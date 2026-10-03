const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    // 1. Standalone CLI Executable (vazus_runner.exe)
    const exe = b.addExecutable(.{
        .name = "vazus_runner",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/main.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    b.installArtifact(exe);

    // 2. Shared Library (DLL) for Python FFI (Native Windows/Linux only)
    if (target.result.os.tag != .wasi) {
        const lib = b.addLibrary(.{
            .name = "vazus_runner",
            .linkage = .dynamic,
            .root_module = b.createModule(.{
                .root_source_file = b.path("src/lib.zig"),
                .target = target,
                .optimize = optimize,
            }),
        });
        b.installArtifact(lib);
    }

    // 3. WASI Preview1 Target Configuration (wasm32-wasi)
    const wasi_target = b.resolveTargetQuery(.{
        .cpu_arch = .wasm32,
        .os_tag = .wasi,
    });
    const wasm_exe = b.addExecutable(.{
        .name = "vazus_runner",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/main.zig"),
            .target = wasi_target,
            .optimize = optimize,
        }),
    });
    const wasm_step = b.step("wasi", "Build WASI module (wasm32-wasi)");
    wasm_step.dependOn(&b.addInstallArtifact(wasm_exe, .{}).step);
}
