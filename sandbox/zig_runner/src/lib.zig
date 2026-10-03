const std = @import("std");
const sandbox = @import("sandbox.zig");
const evaluator = @import("evaluator.zig");

pub export fn check_path_allowed(path: [*:0]const u8) callconv(.c) i32 {
    return sandbox.checkPathAllowed(path);
}

pub export fn execute_sandboxed_snippet(
    code: [*:0]const u8,
    allowed_root: [*:0]const u8,
    out_buf: [*]u8,
    out_len: usize,
) callconv(.c) i32 {
    const root_slice = std.mem.span(allowed_root);
    const sec = sandbox.validatePathWithContext(null, root_slice, false);
    if (sec != .allowed) {
        return -1; // Root outside jail or forbidden
    }

    const code_slice = std.mem.span(code);
    if (code_slice.len == 0) {
        if (out_len > 0) out_buf[0] = 0;
        return 0;
    }

    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const allocator = arena.allocator();

    var eval = evaluator.Evaluator.init(allocator);
    eval.max_loop_iterations = 10000;
    defer eval.deinit();

    eval.eval(code_slice) catch {
        return -2; // Evaluation / syntax error
    };

    const out_slice = eval.stdout_buf.items;
    const copy_len = @min(out_slice.len, if (out_len > 0) out_len - 1 else 0);

    if (copy_len > 0) {
        @memcpy(out_buf[0..copy_len], out_slice[0..copy_len]);
    }
    if (out_len > 0) {
        out_buf[copy_len] = 0;
    }

    return 0;
}

fn parseJsonStringArray(allocator: std.mem.Allocator, list: *std.ArrayList([]const u8), json_str: []const u8) void {
    if (json_str.len == 0) return;
    const parsed = std.json.parseFromSlice([][]const u8, allocator, json_str, .{}) catch return;
    defer parsed.deinit();

    for (parsed.value) |item| {
        const dup = allocator.dupe(u8, item) catch continue;
        list.append(allocator, dup) catch continue;
    }
}

pub export fn vazus_sandbox_init(
    granted_roots_json: [*:0]const u8,
    write_roots_json: [*:0]const u8,
) callconv(.c) ?*anyopaque {
    const allocator = std.heap.page_allocator;
    const ctx = allocator.create(sandbox.SandboxContext) catch return null;
    ctx.* = sandbox.SandboxContext.init(allocator);

    const granted_str = std.mem.span(granted_roots_json);
    parseJsonStringArray(allocator, &ctx.granted_roots, granted_str);

    const write_str = std.mem.span(write_roots_json);
    parseJsonStringArray(allocator, &ctx.write_roots, write_str);

    return @ptrCast(ctx);
}

pub export fn vazus_sandbox_validate_path(
    ctx: ?*anyopaque,
    path: [*:0]const u8,
    is_write: bool,
) callconv(.c) i32 {
    const path_slice = std.mem.span(path);
    const typed_ctx: ?*sandbox.SandboxContext = if (ctx) |p| @ptrCast(@alignCast(p)) else null;
    const res = sandbox.validatePathWithContext(typed_ctx, path_slice, is_write);
    return @intFromEnum(res);
}

pub export fn vazus_sandbox_eval(
    ctx: ?*anyopaque,
    code: [*:0]const u8,
    out_buf: [*]u8,
    out_buf_len: usize,
) callconv(.c) i32 {
    _ = ctx;
    const code_slice = std.mem.span(code);

    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const allocator = arena.allocator();

    var eval = evaluator.Evaluator.init(allocator);
    eval.max_loop_iterations = 10000;
    defer eval.deinit();

    eval.eval(code_slice) catch {
        return -1;
    };

    const out_slice = eval.stdout_buf.items;
    const copy_len = @min(out_slice.len, if (out_buf_len > 0) out_buf_len - 1 else 0);

    if (copy_len > 0) {
        @memcpy(out_buf[0..copy_len], out_slice[0..copy_len]);
    }
    if (out_buf_len > 0) {
        out_buf[copy_len] = 0;
    }

    return @intCast(copy_len);
}

pub export fn vazus_sandbox_free(ctx: ?*anyopaque) callconv(.c) void {
    if (ctx) |p| {
        const typed_ctx: *sandbox.SandboxContext = @ptrCast(@alignCast(p));
        typed_ctx.deinit();
        std.heap.page_allocator.destroy(typed_ctx);
    }
}
