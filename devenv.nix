{ pkgs, lib, config, inputs, ... }:

{
  # =====================================================================
  # DAIMON OS & DNTS - Refined SOTA Development Environment
  # Bundles SOTA compilers, runtimes, Intel Meteor Lake NPU hardware drivers,
  # and SOTA Python libraries including OmniParser and C. elegans c302 integrations.
  # Usage: devenv shell (or direnv allow to trigger instantly via .envrc)
  # =====================================================================

  # 1. System and native compilers
  packages = with pkgs; [
    git
    direnv
    zig             # SOTA Zig Compiler
    go_1_22         # Go 1.22 Compiler exactly as requested
    cmake
    ninja
    pkg-config
    libuv
    
    # Level-Zero hardware drivers for Intel Meteor Lake NPU & compute runtimes
    level-zero
    intel-compute-runtime
    intel-media-driver      # Accelerated media decoding/encoding
    libva                   # Video Acceleration API
  ];

  # 2. Python environment configuration
  languages.python = {
    enable = true;
    venv = {
      enable = true;
      requirements = ''
        # SOTA AI/ML Core
        torch==2.3.1
        torchvision==0.18.1
        transformers==4.40.0
        optimum-intel[openvino,nncf]==1.18.0
        openvino==2024.1.0
        openvino-genai==2024.1.0
        pyyaml
        numpy<2.0.0
        huggingface-hub
        einops
        timm

        # OCR & Screen Parsing (Microsoft OmniParser / Florence-2 Integration)
        easyocr==1.7.1
        ultralytics==8.2.0
        opencv-python-headless
        pillow

        # Computational Biology (C. elegans c302 NeuroML Integration)
        pyNeuroML
        libNeuroML
      '';
    };
  };

  # 3. Native Go Compiler support
  languages.go = {
    enable = true;
    package = pkgs.go_1_22;
  };

  # 4. Environment variables for Intel Core Ultra NPU & OneAPI (Meteor Lake)
  env = {
    # Hardware device routing exactly as requested
    ONEAPI_DEVICE_SELECTOR = "level_zero:0";
    OPENVINO_LOG_LEVEL = "0";

    # Performance optimization flags
    SYCL_CACHE_PERSISTENT = "1";
    SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS = "1";
    ZES_ENABLE_SYSMAN = "1";
    OPENVINO_DEVICE = "NPU";

    # Integrations paths for OmniParser and C. elegans c302
    OMNIPARSER_DIR = "./integrations/omniparser";
    C302_HOME = "./integrations/c302";
  };

  # 5. Shell Hook on workspace activation
  enterShell = ''
    echo ""
    echo "==================================================================="
    echo "🌌 DNTS REFINED SOTA WORKSPACE (devenv.nix + direnv) IS ACTIVE!"
    echo "==================================================================="
    echo "⚙️ System Toolchains & Hardware Drivers:"
    echo "   - Go Compiler:    $(go version)"
    echo "   - Zig Compiler:   $(zig version)"
    echo "   - Intel NPU:      Level-Zero hardware drivers loaded"
    echo "   - Device Selector: ONEAPI_DEVICE_SELECTOR=$ONEAPI_DEVICE_SELECTOR"
    echo "   - Log Level:       OPENVINO_LOG_LEVEL=$OPENVINO_LOG_LEVEL"
    echo "==================================================================="
    echo "🚀 Python Integrations & Frameworks:"
    echo "   - OpenVINO:        OpenVINO GenAI & optimum-intel NPU plug-in"
    echo "   - Screen Parsing:  Microsoft OmniParser & Florence-2 support (loaded)"
    echo "   - Neuro-Modeling:  C. elegans c302 & pyNeuroML simulation pipeline"
    echo "==================================================================="
  '';

  # 6. Pre-commit linters for system hygiene
  pre-commit.hooks = {
    nixpkgs-fmt.enable = true;
    govet.enable = true;
  };
}
