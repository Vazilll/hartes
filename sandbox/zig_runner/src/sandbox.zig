const std = @import("std");
const builtin = @import("builtin");

pub const SecurityResult = enum(i32) {
    allowed = 0,
    forbidden_path = 1,
    outside_jail = 2,
    null_byte = 3,
    read_only_violation = 4,
};

pub const SandboxContext = struct {
    allocator: std.mem.Allocator,
    granted_roots: std.ArrayList([]const u8),
    write_roots: std.ArrayList([]const u8),

    pub fn init(allocator: std.mem.Allocator) SandboxContext {
        return .{
            .allocator = allocator,
            .granted_roots = .empty,
            .write_roots = .empty,
        };
    }

    pub fn deinit(self: *SandboxContext) void {
        for (self.granted_roots.items) |root| {
            self.allocator.free(root);
        }
        self.granted_roots.deinit(self.allocator);

        for (self.write_roots.items) |root| {
            self.allocator.free(root);
        }
        self.write_roots.deinit(self.allocator);
    }

    pub fn addGrantedRoot(self: *SandboxContext, root: []const u8) !void {
        const dup = try self.allocator.dupe(u8, root);
        try self.granted_roots.append(self.allocator, dup);
    }

    pub fn addWriteRoot(self: *SandboxContext, root: []const u8) !void {
        const dup = try self.allocator.dupe(u8, root);
        try self.write_roots.append(self.allocator, dup);
    }
};

fn asciiToLower(c: u8) u8 {
    if (c >= 'A' and c <= 'Z') return c + 32;
    return c;
}

fn containsIgnoreCase(haystack: []const u8, needle: []const u8) bool {
    if (needle.len == 0) return true;
    if (haystack.len < needle.len) return false;
    var i: usize = 0;
    while (i + needle.len <= haystack.len) : (i += 1) {
        var match = true;
        for (needle, 0..) |nc, j| {
            if (asciiToLower(haystack[i + j]) != asciiToLower(nc)) {
                match = false;
                break;
            }
        }
        if (match) return true;
    }
    return false;
}

fn startsWithIgnoreCase(str: []const u8, prefix: []const u8) bool {
    if (str.len < prefix.len) return false;
    for (prefix, 0..) |pc, i| {
        if (asciiToLower(str[i]) != asciiToLower(pc)) return false;
    }
    return true;
}

fn endsWithIgnoreCase(str: []const u8, suffix: []const u8) bool {
    if (str.len < suffix.len) return false;
    const offset = str.len - suffix.len;
    for (suffix, 0..) |sc, i| {
        if (asciiToLower(str[offset + i]) != asciiToLower(sc)) return false;
    }
    return true;
}

pub fn normalizePath(allocator: std.mem.Allocator, raw_path: []const u8) ![]u8 {
    var p = raw_path;
    // Strip Windows Extended-Length / UNC Prefix \\?\ or //?/
    if (p.len >= 4 and ((p[0] == '\\' and p[1] == '\\' and p[2] == '?' and p[3] == '\\') or
        (p[0] == '/' and p[1] == '/' and p[2] == '?' and p[3] == '/')))
    {
        p = p[4..];
    }

    // Allocate working buffer
    var buf = try allocator.alloc(u8, p.len);
    errdefer allocator.free(buf);

    for (p, 0..) |c, i| {
        if (c == '\\') {
            buf[i] = '/';
        } else {
            buf[i] = c;
        }
    }

    // Normalize Windows drive letter to uppercase
    if (buf.len >= 2 and buf[1] == ':' and ((buf[0] >= 'a' and buf[0] <= 'z') or (buf[0] >= 'A' and buf[0] <= 'Z'))) {
        if (buf[0] >= 'a' and buf[0] <= 'z') {
            buf[0] = buf[0] - 32;
        }
    }

    // Split components and resolve . and ..
    var components: std.ArrayList([]const u8) = .empty;
    defer components.deinit(allocator);

    var has_drive = false;
    var drive_prefix: []const u8 = "";
    var remainder = buf[0..];

    if (remainder.len >= 2 and remainder[1] == ':') {
        has_drive = true;
        if (remainder.len >= 3 and remainder[2] == '/') {
            drive_prefix = remainder[0..2]; // e.g. "C:"
            remainder = remainder[3..];
        } else {
            drive_prefix = remainder[0..2];
            remainder = remainder[2..];
        }
    } else if (remainder.len > 0 and remainder[0] == '/') {
        remainder = remainder[1..];
    }

    var it = std.mem.splitScalar(u8, remainder, '/');
    while (it.next()) |part| {
        if (part.len == 0 or std.mem.eql(u8, part, ".")) {
            continue;
        } else if (std.mem.eql(u8, part, "..")) {
            if (components.items.len > 0) {
                _ = components.pop();
            } else {
                // Traversal escape outside root!
                allocator.free(buf);
                return error.TraversalEscape;
            }
        } else {
            try components.append(allocator, part);
        }
    }

    var result: std.ArrayList(u8) = .empty;
    errdefer result.deinit(allocator);

    if (has_drive) {
        try result.appendSlice(allocator, drive_prefix);
        try result.append(allocator, '/');
    } else if (raw_path.len > 0 and (raw_path[0] == '/' or raw_path[0] == '\\')) {
        try result.append(allocator, '/');
    }

    for (components.items, 0..) |comp, i| {
        if (i > 0 or has_drive) {
            if (i > 0) try result.append(allocator, '/');
        }
        try result.appendSlice(allocator, comp);
    }

    allocator.free(buf);
    return result.toOwnedSlice(allocator);
}

pub fn isPathForbidden(normalized: []const u8) bool {
    // 1. windows/system32
    if (containsIgnoreCase(normalized, "windows/system32")) return true;

    // 2. /etc/ or etc/ at start
    if (containsIgnoreCase(normalized, "/etc/") or startsWithIgnoreCase(normalized, "etc/") or
        startsWithIgnoreCase(normalized, "/etc") or endsWithIgnoreCase(normalized, "/etc") or
        std.ascii.eqlIgnoreCase(normalized, "etc"))
    {
        return true;
    }

    // 3. .git
    if (containsIgnoreCase(normalized, "/.git/") or endsWithIgnoreCase(normalized, "/.git") or
        startsWithIgnoreCase(normalized, ".git/") or std.ascii.eqlIgnoreCase(normalized, ".git"))
    {
        return true;
    }

    // 4. AGENTS.md
    if (endsWithIgnoreCase(normalized, "/agents.md") or std.ascii.eqlIgnoreCase(normalized, "agents.md")) {
        return true;
    }

    return false;
}

pub fn isWithinRoot(path: []const u8, root: []const u8) bool {
    if (!startsWithIgnoreCase(path, root)) return false;
    if (path.len == root.len) return true;
    if (root.len > 0 and root[root.len - 1] == '/') return true;
    if (path.len > root.len and path[root.len] == '/') return true;
    return false;
}

pub fn validatePathWithContext(ctx: ?*SandboxContext, raw_path: []const u8, is_write: bool) SecurityResult {
    // Check for null byte inside path
    for (raw_path) |c| {
        if (c == 0) return .null_byte;
    }

    // Check for empty or whitespace-only
    var has_content = false;
    for (raw_path) |c| {
        if (c != ' ' and c != '\t' and c != '\r' and c != '\n') {
            has_content = true;
            break;
        }
    }
    if (!has_content) return .outside_jail;

    // Normalize path
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const allocator = arena.allocator();

    const normalized = normalizePath(allocator, raw_path) catch |err| {
        if (err == error.TraversalEscape) return .outside_jail;
        return .outside_jail;
    };

    // Check strictly forbidden rules
    if (isPathForbidden(normalized)) {
        return .forbidden_path;
    }

    // Check against context if provided
    if (ctx) |context| {
        var matched_granted = false;
        for (context.granted_roots.items) |root| {
            const norm_root = normalizePath(allocator, root) catch continue;
            if (isWithinRoot(normalized, norm_root)) {
                matched_granted = true;
                break;
            }
        }

        // Also check default roots: C:/vazus and ~/.gemini
        if (!matched_granted) {
            if (isWithinDefaultJail(normalized)) {
                matched_granted = true;
            }
        }

        if (!matched_granted) return .outside_jail;

        if (is_write) {
            // Check write roots if write_roots list is not empty
            if (context.write_roots.items.len > 0) {
                var matched_write = false;
                for (context.write_roots.items) |wroot| {
                    const norm_wroot = normalizePath(allocator, wroot) catch continue;
                    if (isWithinRoot(normalized, norm_wroot)) {
                        matched_write = true;
                        break;
                    }
                }
                if (!matched_write) return .read_only_violation;
            }
        }

        return .allowed;
    }

    // Default static jail check: C:/vazus and ~/.gemini
    if (isWithinDefaultJail(normalized)) {
        return .allowed;
    }

    return .outside_jail;
}

fn isUserHomeGemini(normalized: []const u8) bool {
    var rem: []const u8 = normalized;

    // Check Windows drive letter + /Users/ (e.g. "C:/Users/" or any drive letter)
    if (rem.len >= 9 and ((rem[0] >= 'a' and rem[0] <= 'z') or (rem[0] >= 'A' and rem[0] <= 'Z')) and rem[1] == ':') {
        if (startsWithIgnoreCase(rem[2..], "/Users/")) {
            rem = rem[9..]; // Skip "<drive>:/Users/"
        } else {
            return false;
        }
    } else if (startsWithIgnoreCase(rem, "/home/")) {
        rem = rem[6..]; // Skip "/home/"
    } else if (startsWithIgnoreCase(rem, "/Users/")) {
        rem = rem[7..]; // Skip "/Users/"
    } else {
        return false;
    }

    // rem is now "<username>/..."
    // Find the delimiter after username
    const slash_idx = std.mem.indexOfScalar(u8, rem, '/') orelse return false;
    if (slash_idx == 0) return false; // empty username

    const after_user = rem[slash_idx + 1 ..];
    // after_user must be strictly within ".gemini" root (e.g. ".gemini" or ".gemini/...")
    return isWithinRoot(after_user, ".gemini");
}

fn isWithinDefaultJail(normalized: []const u8) bool {
    // 1. C:/vazus
    if (isWithinRoot(normalized, "C:/vazus")) return true;

    // 2. ~/.gemini
    if (isWithinRoot(normalized, "~/.gemini")) return true;

    // 3. User home directory variations (e.g. C:/Users/<user>/.gemini)
    if (isUserHomeGemini(normalized)) return true;

    return false;
}

pub fn checkPathAllowed(path_z: [*:0]const u8) i32 {
    const slice = std.mem.span(path_z);
    const res = validatePathWithContext(null, slice, false);
    return if (res == .allowed) 1 else 0;
}
