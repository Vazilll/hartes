const std = @import("std");
const builtin = @import("builtin");
const sandbox = @import("sandbox.zig");
const evaluator = @import("evaluator.zig");

const is_windows = builtin.os.tag == .windows;

const kernel32 = if (is_windows) struct {
    extern "kernel32" fn GetStdHandle(nStdHandle: i32) callconv(.winapi) ?*anyopaque;
    extern "kernel32" fn WriteFile(hFile: ?*anyopaque, lpBuffer: [*]const u8, nNumberOfBytesToWrite: u32, lpNumberOfBytesWritten: ?*u32, lpOverlapped: ?*anyopaque) callconv(.winapi) i32;
} else struct {};

fn writeStdout(bytes: []const u8) void {
    if (bytes.len == 0) return;
    if (is_windows) {
        const handle = kernel32.GetStdHandle(-11); // STD_OUTPUT_HANDLE = -11
        var written: u32 = 0;
        _ = kernel32.WriteFile(handle, bytes.ptr, @intCast(bytes.len), &written, null);
    } else {
        std.debug.print("{s}", .{bytes});
    }
}

fn writeStderr(bytes: []const u8) void {
    if (bytes.len == 0) return;
    if (is_windows) {
        const handle = kernel32.GetStdHandle(-12); // STD_ERROR_HANDLE = -12
        var written: u32 = 0;
        _ = kernel32.WriteFile(handle, bytes.ptr, @intCast(bytes.len), &written, null);
    } else {
        std.debug.print("{s}", .{bytes});
    }
}

pub fn main(init: std.process.Init) !void {
    var it = try init.minimal.args.iterateAllocator(init.gpa);
    defer it.deinit();

    _ = it.next(); // Skip executable path

    var root_arg: ?[]const u8 = null;
    var eval_arg: ?[]const u8 = null;
    var is_version = false;

    while (it.next()) |arg| {
        if (std.mem.eql(u8, arg, "--version") or std.mem.eql(u8, arg, "-v")) {
            is_version = true;
        } else if (std.mem.eql(u8, arg, "--root")) {
            root_arg = it.next();
        } else if (std.mem.eql(u8, arg, "--eval")) {
            if (it.next()) |next_token| {
                eval_arg = next_token;
            } else {
                eval_arg = "";
            }
        }
    }

    if (is_version) {
        writeStdout("vazus-runner 1.0.0 (Zig Sandbox Micro-Runner)\n");
        return;
    }

    if (root_arg == null) {
        writeStderr("Error: required parameter --root <PATH> is missing\n");
        std.process.exit(1);
    }

    const root_val = root_arg.?;
    const root_sec = sandbox.validatePathWithContext(null, root_val, false);
    if (root_sec != .allowed) {
        writeStderr("Error: specified root is forbidden or outside capability jail\n");
        std.process.exit(1);
    }

    if (eval_arg == null) {
        writeStderr("Error: missing --eval <CODE> parameter\n");
        std.process.exit(1);
    }

    const code = eval_arg.?;
    if (code.len == 0) {
        // Empty evaluation returns exit code 0 cleanly
        return;
    }

    const allocator = init.gpa;
    var eval_engine = evaluator.Evaluator.init(allocator);
    defer eval_engine.deinit();

    eval_engine.eval(code) catch |err| {
        switch (err) {
            error.SyntaxError => writeStderr("SyntaxError: invalid code syntax in sandboxed evaluation\n"),
            error.DivisionByZero => writeStderr("ZeroDivisionError: division by zero in evaluation\n"),
            error.ExecutionTimeout => writeStderr("TimeoutError: sandboxed execution exceeded maximum iterations\n"),
            else => writeStderr("EvaluationError: sandboxed execution failed\n"),
        }
        std.process.exit(1);
    };

    if (eval_engine.stdout_buf.items.len > 0) {
        writeStdout(eval_engine.stdout_buf.items);
    }
}
