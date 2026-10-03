import pytest
from pathlib import Path
from vazus_core.runtime.vm_controller import VirtualizationLab, VMProvider, ScreenAnalyzer, SandboxProvider, VBoxProvider, VMInfo, SnapshotInfo, VMState

@pytest.fixture
def lab():
    return VirtualizationLab()

def test_health_check(lab):
    health = lab.health_check()
    assert "virtualbox" in health
    assert "hyperv" in health
    assert "sandbox" in health
    assert "ocr" in health

def test_vbox_list(lab):
    if lab.vbox.available:
        vms = lab.vbox.list_vms()
        assert isinstance(vms, list)

def test_screenshot_ocr(lab, tmp_path):
    if not lab.screen.available:
        pytest.skip("RapidOCR not available")
        
    # Create a dummy image
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (100, 30), color = (73, 109, 137))
    d = ImageDraw.Draw(img)
    d.text((10,10), "Login Prompt", fill=(255,255,0))
    p = tmp_path / "test.png"
    img.save(p)
    
    result = lab.screen.analyze(p)
    assert result.has_text
    assert "login" in result.ocr_text.lower()
    assert result.detected_state == "login_prompt"

def test_sandbox_wsb_generation(lab, tmp_path):
    if not lab.sandbox.available:
        pytest.skip("Windows Sandbox not available")
        
    mapped = [{"host": str(tmp_path), "guest": r"C:\Temp", "readonly": True}]
    wsb = lab.sandbox.generate_wsb(mapped, "cmd.exe")
    assert wsb.exists()
    content = wsb.read_text()
    assert "<MappedFolders>" in content
    assert "<HostFolder>" in content
    assert "cmd.exe" in content

def test_create_and_delete_vm(lab):
    if not lab.vbox.available:
        pytest.skip("VirtualBox not available")
    
    test_vm = "test_lab_vm"
    
    try:
        lab.vbox.delete_vm(test_vm)
    except Exception:
        pass
        
    vm = lab.create_lab_vm(test_vm, "Ubuntu_64", memory_mb=512, cpus=1, disk_gb=1)
    assert vm.name == test_vm
    assert vm.state == VMState.POWEROFF
    assert vm.provider == VMProvider.VIRTUALBOX
    
    snaps = lab.vbox.list_snapshots(test_vm)
    assert len(snaps) == 0
    
    lab.vbox.create_snapshot(test_vm, "snap1")
    snaps = lab.vbox.list_snapshots(test_vm)
    assert len(snaps) == 1
    assert snaps[0].name == "snap1"
    
    lab.vbox.delete_vm(test_vm)
    
    try:
        lab.vbox.get_vm_info(test_vm)
        pytest.fail("VM should have been deleted")
    except Exception as e:
        assert "not found" in str(e).lower()

def test_screen_analyzer():
    analyzer = ScreenAnalyzer()
    assert analyzer.detect_state("Please enter your login and password") == "login_prompt"
    assert analyzer.detect_state("kernel panic - not syncing: VFS") == "crash"
    assert analyzer.detect_state("GNU GRUB version 2.06") == "boot_menu"
    assert analyzer.detect_state("") == "blank"
    assert analyzer.detect_state("Hello World!") == "desktop"
