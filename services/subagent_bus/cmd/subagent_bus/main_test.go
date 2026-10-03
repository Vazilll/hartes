package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestIsPathAllowed(t *testing.T) {
	home, err := os.UserHomeDir()
	if err != nil {
		t.Fatalf("failed to get user home dir: %v", err)
	}
	geminiRoot := filepath.Join(home, ".gemini")

	tests := []struct {
		name     string
		path     string
		expected bool
	}{
		// ---------------------------------------------------------
		// Category 1: Allowed workspace root & descendants
		// ---------------------------------------------------------
		{"EmptyString", "", true},
		{"VazusRoot_Upper", `C:\vazus`, true},
		{"VazusRoot_Lower", `c:\vazus`, true},
		{"VazusRoot_TrailingBackslash", `C:\vazus\`, true},
		{"VazusRoot_ForwardSlash", `C:/vazus`, true},
		{"VazusSubdir", `C:\vazus\services\subagent_bus`, true},
		{"VazusDeepSubdir", `c:/vazus/internal/actor`, true},
		{"VazusUNC", `\\?\C:\vazus`, true},
		{"VazusUNC_Subdir", `\\?\C:\vazus\services`, true},
		{"VazusDotSlash", `C:\vazus\.\services`, true},
		{"VazusDotDotInternal", `C:\vazus\services\..\internal`, true},

		// ---------------------------------------------------------
		// Category 2: Allowed Gemini root & descendants (Absolute & Literal Tilde)
		// ---------------------------------------------------------
		{"GeminiRoot_Absolute", geminiRoot, true},
		{"GeminiSubdir_Absolute", filepath.Join(geminiRoot, "config", "skills"), true},
		{"GeminiRoot_LiteralTilde", "~/.gemini", true},
		{"GeminiRoot_LiteralTildeTrailingSlash", "~/.gemini/", true},
		{"GeminiRoot_LiteralTildeBackslash", `~\.gemini`, true},
		{"GeminiRoot_LiteralTildeBackslashTrailing", `~\.gemini\`, true},
		{"GeminiSubdir_LiteralTilde", "~/.gemini/sub", true},
		{"GeminiDeepSubdir_LiteralTilde", "~/.gemini/antigravity/scratch", true},
		{"GeminiSubdir_LiteralTildeBackslash", `~\.gemini\sub`, true},

		// ---------------------------------------------------------
		// Category 3: Rejected Sibling Prefix Exploits (Fail-Closed R4.1)
		// ---------------------------------------------------------
		{"VazusEvil_Sibling", `C:\vazus_evil`, false},
		{"Vazus2_Sibling", `C:\vazus2`, false},
		{"VazusBak_Sibling", `C:\vazus.bak`, false},
		{"VazusDash_Sibling", `C:\vazus-other`, false},
		{"VazusEvil_UNC", `\\?\C:\vazus_evil`, false},
		{"Vazus2_UNC", `\\?\C:\vazus2`, false},
		{"GeminiEvil_Absolute", filepath.Join(home, ".gemini_evil"), false},
		{"Gemini2_Absolute", filepath.Join(home, ".gemini2"), false},
		{"GeminiBackup_Absolute", filepath.Join(home, ".gemini_backup"), false},
		{"GeminiEvil_LiteralTilde", "~/.gemini_evil", false},
		{"Gemini2_LiteralTilde", "~/.gemini2", false},
		{"GeminiBackup_LiteralTilde", "~/.gemini_backup", false},
		{"GeminiEvil_LiteralTildeBackslash", `~\.gemini_evil`, false},
		{"GeminiEvil_OtherDrive", `C:\evil\.gemini\payload.exe`, false},
		{"GeminiEvil_ProgramData", `C:\ProgramData\.gemini_evil\hack.exe`, false},

		// ---------------------------------------------------------
		// Category 4: Rejected Invariant Targets (Zero-Tampering Security Invariant)
		// ---------------------------------------------------------
		{"Invariant_AgentsMd", `C:\vazus\AGENTS.md`, false},
		{"Invariant_AgentsMd_Lower", `c:\vazus\agents.md`, false},
		{"Invariant_AgentsMd_Subdir", `C:\vazus\subdir\AGENTS.md`, false},
		{"Invariant_AgentsMd_UNC", `\\?\C:\vazus\AGENTS.md`, false},
		{"Invariant_AgentsMd_LiteralTilde", `~/.gemini/AGENTS.md`, false},
		{"Invariant_GitDir", `C:\vazus\.git`, false},
		{"Invariant_GitDir_TrailingSlash", `C:\vazus\.git\`, false},
		{"Invariant_GitConfig", `C:\vazus\.git\config`, false},
		{"Invariant_GitHead", `C:\vazus\.git\HEAD`, false},
		{"Invariant_GitSubdir", `C:\vazus\services\.git\config`, false},
		{"Invariant_Git_UNC", `\\?\C:\vazus\.git\config`, false},
		{"Invariant_Git_UNC_Dir", `\\?\C:\vazus\.git`, false},
		{"Invariant_WindowsSystem32_Cmd", `C:\Windows\System32\cmd.exe`, false},
		{"Invariant_WindowsSystem32_DriversEtc", `C:\Windows\System32\drivers\etc\hosts`, false},
		{"Invariant_EtcPasswd", `/etc/passwd`, false},
		{"Invariant_EtcPasswd_Relative", `etc/passwd`, false},
		{"Invariant_EtcShadow", `/etc/shadow`, false},

		// ---------------------------------------------------------
		// Category 5: Rejected Traversal & Arbitrary Host Filesystem Escapes
		// ---------------------------------------------------------
		{"WindowsRoot", `C:\Windows`, false},
		{"WindowsSystem32", `C:\Windows\System32`, false},
		{"DriveCRoot", `C:\`, false},
		{"DriveDRoot", `D:\`, false},
		{"ProgramFiles", `C:\Program Files`, false},
		{"RelativeEscapeEtc", `..\..\..\..\..\..\etc`, false},
		{"DotDotEscapeWindows", `C:\vazus\..\Windows`, false},
		{"DotDotEscapeDriveRoot", `C:\vazus\..`, false},
		{"WindowsUNC", `\\?\C:\Windows`, false},
		{"TildeOnly", "~", false},
		{"TildeSlashOnly", "~/", false},
		{"TildeBackslashOnly", `~\`, false},
		{"TildeDesktop", "~/Desktop", false},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := isPathAllowed(tc.path)
			if got != tc.expected {
				t.Errorf("isPathAllowed(%q) = %v, expected %v", tc.path, got, tc.expected)
			}
		})
	}
}

func TestIsPathAllowed_CwdIndependence(t *testing.T) {
	origCwd, err := os.Getwd()
	if err != nil {
		t.Fatalf("failed to get current working directory: %v", err)
	}
	defer func() {
		_ = os.Chdir(origCwd)
	}()

	home, err := os.UserHomeDir()
	if err != nil {
		t.Fatalf("failed to get user home dir: %v", err)
	}

	testDirs := []string{
		`C:\vazus`,
		home,
		os.TempDir(),
	}

	for _, dir := range testDirs {
		if err := os.Chdir(dir); err != nil {
			t.Logf("skipping unavailable cwd %q: %v", dir, err)
			continue
		}

		t.Run("CWD_"+filepath.Base(dir), func(t *testing.T) {
			// Whitelisted vectors must ALWAYS be allowed regardless of CWD
			if !isPathAllowed("~/.gemini") {
				t.Errorf("in cwd %q: isPathAllowed(\"~/.gemini\") = false, expected true", dir)
			}
			if !isPathAllowed("~/.gemini/sub") {
				t.Errorf("in cwd %q: isPathAllowed(\"~/.gemini/sub\") = false, expected true", dir)
			}
			if !isPathAllowed(`C:\vazus`) {
				t.Errorf("in cwd %q: isPathAllowed(`C:\\vazus`) = false, expected true", dir)
			}
			if !isPathAllowed(`C:\vazus\services`) {
				t.Errorf("in cwd %q: isPathAllowed(`C:\\vazus\\services`) = false, expected true", dir)
			}

			// Adversarial attack vectors must ALWAYS be rejected regardless of CWD
			if isPathAllowed("~/.gemini_evil") {
				t.Errorf("in cwd %q: isPathAllowed(\"~/.gemini_evil\") = true, expected false", dir)
			}
			if isPathAllowed("~/.gemini2") {
				t.Errorf("in cwd %q: isPathAllowed(\"~/.gemini2\") = true, expected false", dir)
			}
			if isPathAllowed("~/.gemini_backup") {
				t.Errorf("in cwd %q: isPathAllowed(\"~/.gemini_backup\") = true, expected false", dir)
			}
			if isPathAllowed(`C:\vazus\AGENTS.md`) {
				t.Errorf("in cwd %q: isPathAllowed(`C:\\vazus\\AGENTS.md`) = true, expected false", dir)
			}
			if isPathAllowed(`C:\vazus\.git\config`) {
				t.Errorf("in cwd %q: isPathAllowed(`C:\\vazus\\.git\\config`) = true, expected false", dir)
			}
			if isPathAllowed(`C:\vazus\.git`) {
				t.Errorf("in cwd %q: isPathAllowed(`C:\\vazus\\.git`) = true, expected false", dir)
			}
			if isPathAllowed(`\\?\C:\vazus\AGENTS.md`) {
				t.Errorf("in cwd %q: isPathAllowed(`\\\\?\\C:\\vazus\\AGENTS.md`) = true, expected false", dir)
			}
			if isPathAllowed(`C:\vazus_evil`) {
				t.Errorf("in cwd %q: isPathAllowed(`C:\\vazus_evil`) = true, expected false", dir)
			}
			if isPathAllowed(`C:\Windows\System32\cmd.exe`) {
				t.Errorf("in cwd %q: isPathAllowed(`C:\\Windows\\System32\\cmd.exe`) = true, expected false", dir)
			}
			if isPathAllowed("/etc/passwd") {
				t.Errorf("in cwd %q: isPathAllowed(\"/etc/passwd\") = true, expected false", dir)
			}
		})
	}
}

func TestCLIProcessWorkdirEnforcement(t *testing.T) {
	exePath := `C:\vazus\bin\subagent_bus.exe`
	if _, err := os.Stat(exePath); os.IsNotExist(err) {
		t.Skipf("compiled binary %s not found, skipping CLI subprocess test", exePath)
	}

	home, err := os.UserHomeDir()
	if err != nil {
		t.Fatalf("failed to get user home dir: %v", err)
	}

	cliTests := []struct {
		name         string
		cwd          string
		workdir      string
		expectedExit int
	}{
		// Rejections from CWD C:\vazus
		{"Reject_GeminiEvil_FromVazus", `C:\vazus`, "~/.gemini_evil", 1},
		{"Reject_Gemini2_FromVazus", `C:\vazus`, "~/.gemini2", 1},
		{"Reject_GeminiBackup_FromVazus", `C:\vazus`, "~/.gemini_backup", 1},
		{"Reject_AgentsMd_FromVazus", `C:\vazus`, `C:\vazus\AGENTS.md`, 1},
		{"Reject_GitConfig_FromVazus", `C:\vazus`, `C:\vazus\.git\config`, 1},
		{"Reject_GitDir_FromVazus", `C:\vazus`, `C:\vazus\.git`, 1},
		{"Reject_UNCAgentsMd_FromVazus", `C:\vazus`, `\\?\C:\vazus\AGENTS.md`, 1},
		{"Reject_VazusEvil_FromVazus", `C:\vazus`, `C:\vazus_evil`, 1},
		{"Reject_Vazus2_FromVazus", `C:\vazus`, `C:\vazus2`, 1},
		{"Reject_WindowsCmd_FromVazus", `C:\vazus`, `C:\Windows\System32\cmd.exe`, 1},
		{"Reject_EtcPasswd_FromVazus", `C:\vazus`, `/etc/passwd`, 1},

		// Rejections from CWD C:\Users\Vaz
		{"Reject_GeminiEvil_FromHome", home, "~/.gemini_evil", 1},
		{"Reject_AgentsMd_FromHome", home, `C:\vazus\AGENTS.md`, 1},
		{"Reject_GitConfig_FromHome", home, `C:\vazus\.git\config`, 1},

		// Allowed from CWD C:\vazus
		{"Allow_VazusRoot_FromVazus", `C:\vazus`, `C:\vazus`, 0},
		{"Allow_VazusServices_FromVazus", `C:\vazus`, `C:\vazus\services`, 0},
		{"Allow_UNCVazus_FromVazus", `C:\vazus`, `\\?\C:\vazus`, 0},
		{"Allow_Gemini_FromVazus", `C:\vazus`, "~/.gemini", 0},
		{"Allow_GeminiSub_FromVazus", `C:\vazus`, "~/.gemini/sub", 0},

		// Allowed from CWD C:\Users\Vaz
		{"Allow_Gemini_FromHome", home, "~/.gemini", 0},
		{"Allow_GeminiSub_FromHome", home, "~/.gemini/sub", 0},
		{"Allow_VazusRoot_FromHome", home, `C:\vazus`, 0},
	}

	for _, tc := range cliTests {
		t.Run(tc.name, func(t *testing.T) {
			cmd := exec.Command(exePath, "--workdir", tc.workdir)
			cmd.Dir = tc.cwd
			cmd.Stdin = strings.NewReader("")
			err := cmd.Run()

			actualExit := 0
			if err != nil {
				if exitErr, ok := err.(*exec.ExitError); ok {
					actualExit = exitErr.ExitCode()
				} else {
					t.Fatalf("failed to execute process %s: %v", exePath, err)
				}
			}

			if actualExit != tc.expectedExit {
				t.Errorf("CLI exec with workdir %q in cwd %q: got exit code %d, expected %d",
					tc.workdir, tc.cwd, actualExit, tc.expectedExit)
			}
		})
	}
}
