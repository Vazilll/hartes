{
  description = "DNTS Cognitive Platform — Unified Nix Flake Orchestration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";

    # Modern, optimized Rust builder caching dependency layers
    crane = {
      url = "github:ipetkov/crane";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Overlays for specific Rust toolchains (including bare-metal/nightly)
    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Fully reproducible Python packaging builder
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, crane, rust-overlay, poetry2nix }@inputs:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [
            rust-overlay.overlays.default
            poetry2nix.overlays.default
          ];
        };

        # 1. NIGHTLY RUST TOOLCHAIN (supporting no_std/bare-metal configurations for Daimon OS)
        rustToolchain = pkgs.rust-bin.nightly.latest.default.override {
          extensions = [ "rust-src" "llvm-tools-preview" "rust-analyzer" ];
          targets = [ "x86_64-unknown-none" "aarch64-unknown-none" ];
        };

        # Initialize Crane builder bound to our Nightly Rust Toolchain
        craneLib = (crane.mkLib pkgs).overrideToolchain rustToolchain;

        # Source filtering to prevent rebuilds on unrelated documentation or temp changes
        daimonSrc = pkgs.lib.cleanSourceWith {
          src = ./daimon;
          filter = path: type:
            (pkgs.lib.hasSuffix ".rs" path) ||
            (pkgs.lib.hasSuffix ".toml" path) ||
            (pkgs.lib.hasSuffix ".lock" path) ||
            (craneLib.filterCargoSources path type);
        };

        # Shared Rust compilation arguments
        daimonCommonArgs = {
          src = daimonSrc;
          strictDeps = true;
          buildInputs = with pkgs; [
            openssl
            sqlite
          ] ++ pkgs.lib.optionals pkgs.stdenv.isDarwin [
            pkgs.darwin.apple_sdk.frameworks.Security
            pkgs.darwin.apple_sdk.frameworks.SystemConfiguration
          ];
          nativeBuildInputs = with pkgs; [
            pkg-config
          ];
        };

        # Cache Daimon dependency cargo builds to speed up packaging
        cargoArtifacts = craneLib.buildDepsOnly daimonCommonArgs;

        # 2. RUST DAIMON OS COMPONENTS (rt, soul, cortex)
        daimon-rt = craneLib.buildPackage (daimonCommonArgs // {
          inherit cargoArtifacts;
          pname = "daimon-rt";
          cargoExtraArgs = "-p rt";
          meta.description = "DAIMON OS — Core High Performance Runtime (Bare-metal Target)";
        });

        daimon-soul = craneLib.buildPackage (daimonCommonArgs // {
          inherit cargoArtifacts;
          pname = "daimon-soul";
          cargoExtraArgs = "-p soul";
          meta.description = "DAIMON OS — Cognitive Homeostatic Agent Controller (Soul)";
        });

        daimon-cortex = craneLib.buildPackage (daimonCommonArgs // {
          inherit cargoArtifacts;
          pname = "daimon-cortex";
          cargoExtraArgs = "-p cortex";
          meta.description = "DAIMON OS — Deep Reasoning & LLM Interface Kernel (Cortex)";
        });

        # 3. GO MCP SERVER (gomcp) with all 89 tools (subPackages mapped cleanly)
        gomcp = pkgs.buildGoModule {
          pname = "gomcp";
          version = "5.3.0";
          src = ./gomcp;

          # To rebuild this Go package cleanly in a Nix sandbox, run nix build.
          # If dependencies change, update this hash (or set to pkgs.lib.fakeHash)
          vendorHash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="; 
          
          # Allows proxy fetching during building if vendorHash needs to be computed
          proxyVendor = true;

          nativeBuildInputs = [ pkgs.go ];
          buildInputs = [ pkgs.sqlite ];

          subPackages = [ 
            "cmd/dnts-core" 
            "cmd/dnts-memory" 
            "cmd/dnts-reason" 
            "cmd/dnts-agent" 
            "cmd/dnts-server" 
          ];

          meta.description = "Go MCP Server exposing consolidated cognitive tools";
        };

        # 4. ZIG NEUROFORGE (Zig ML-kernels compiled with native Zig toolchain)
        neuroforge = pkgs.stdenv.mkDerivation {
          pname = "neuroforge";
          version = "1.0.0";
          src = ./daimon/forge;

          nativeBuildInputs = [ pkgs.zig ];

          buildPhase = ''
            export HOME=$TMPDIR
            zig build -Doptimize=ReleaseFast
          '';

          installPhase = ''
            mkdir -p $out/lib
            if [ -d "zig-out/lib" ]; then
              cp -r zig-out/lib/* $out/lib/
            fi
            if [ -f "forge_kernels.lib" ]; then
              cp forge_kernels.lib $out/lib/
            fi
          '';

          meta.description = "Zig NeuroForge — Matrix and Tensor ML-kernels for Daimon OS";
        };

        # 5. PYTHON HERMES AGENT & NPU SERVICES (poetry2nix for reproducible builds)
        pythonEnv = pkgs.poetry2nix.mkPoetryEnv {
          projectDir = ./_research/hermes-agent;
          pyproject = ./_research/hermes-agent/pyproject.toml;
          # Point to poetry lockfile. If poetry.lock is not pre-generated, Nix handles
          # python dependencies using the pyproject.toml requirements.
          poetrylock = ./_research/hermes-agent/poetry.lock;
          overrides = pkgs.poetry2nix.defaultPoetryOverrides.extend (selfPy: superPy: {
            # Inject native compile overrides or package-specific fixes here
          });
        };

        hermes-agent = pkgs.poetry2nix.mkPoetryApplication {
          projectDir = ./_research/hermes-agent;
          pyproject = ./_research/hermes-agent/pyproject.toml;
          poetrylock = ./_research/hermes-agent/poetry.lock;
          meta.description = "Python-agent Hermes — Nous Research Autonomous Execution Layer";
        };

      in {
        # Exported outputs of the Nix Flake
        packages = {
          inherit daimon-rt daimon-soul daimon-cortex gomcp neuroforge hermes-agent;

          # Default unified bundle combining all services into a single directory prefix
          default = pkgs.symlinkJoin {
            name = "dnts-unified-platform";
            paths = [
              daimon-rt
              daimon-soul
              daimon-cortex
              gomcp
              neuroforge
              hermes-agent
            ];
          };
        };

        # Fully declarative, sandboxed development shells
        devShells.default = pkgs.mkShell {
          name = "dnts-platform-dev-shell";

          buildInputs = with pkgs; [
            # Rust Nightly toolchain & cargo tools
            rustToolchain
            cargo-binutils
            cargo-expand

            # Go development
            go
            gopls

            # Zig compiler
            zig

            # Python Poetry reproducible setup
            pythonEnv
            poetry

            # Databases & Native tools
            sqlite
            openssl
            pkg-config
            git
            ripgrep
            fd
          ];

          shellHook = ''
            echo "======================================================================"
            echo "   🌌 DNTS UNIFIED COGNITIVE DEVSHELL — REPRODUCIBLE NIX FLAKE"
            echo "======================================================================"
            echo "   * Rust Nightly Target : $(rustc --version)"
            echo "   * Go Compiler Target  : $(go version)"
            echo "   * Zig Compiler Target : $(zig version)"
            echo "   * Python reproducible env via poetry2nix is loaded and ready"
            echo "======================================================================"
          '';

          # Cross compile target configurations
          CARGO_TARGET_X86_64_UNKNOWN_NONE_LINKER = "rust-lld";
          CARGO_TARGET_AARCH64_UNKNOWN_NONE_LINKER = "rust-lld";
          RUST_SRC_PATH = "${rustToolchain}/lib/rustlib/src/rust/library";
        };
      }
    );
}
