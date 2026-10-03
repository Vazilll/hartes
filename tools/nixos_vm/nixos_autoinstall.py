import subprocess
import time

SCANCODES = {
    'a': ['1e', '9e'], 'b': ['30', 'b0'], 'c': ['2e', 'ae'], 'd': ['20', 'a0'], 'e': ['12', '92'],
    'f': ['21', 'a1'], 'g': ['22', 'a2'], 'h': ['23', 'a3'], 'i': ['17', '97'], 'j': ['24', 'a4'],
    'k': ['25', 'a5'], 'l': ['26', 'a6'], 'm': ['32', 'b2'], 'n': ['31', 'b1'], 'o': ['18', '98'],
    'p': ['19', '99'], 'q': ['10', '90'], 'r': ['13', '93'], 's': ['1f', '9f'], 't': ['14', '94'],
    'u': ['16', '96'], 'v': ['2f', 'af'], 'w': ['11', '91'], 'x': ['2d', 'ad'], 'y': ['15', '95'],
    'z': ['2c', 'ac'], '1': ['02', '82'], '2': ['03', '83'], '3': ['04', '84'], '4': ['05', '85'],
    '5': ['06', '86'], '6': ['07', '87'], '7': ['08', '88'], '8': ['09', '89'], '9': ['0a', '8a'],
    '0': ['0b', '8b'], ' ': ['39', 'b9'], '\n': ['1c', '9c'], '-': ['0c', '8c'], '=': ['0d', '8d'],
    ':': ['2a', '27', 'a7', 'aa'], ';': ['27', 'a7'], '/': ['35', 'b5'], '.': ['34', 'b4'],
    '|': ['2a', '2b', 'ab', 'aa'], '\"': ['2a', '28', 'a8', 'aa'], '_': ['2a', '0c', '8c', 'aa']
}

def type_text(vm_name, text):
    vbox = r'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
    for ch in text:
        if ch in SCANCODES:
            subprocess.run([vbox, 'controlvm', vm_name, 'keyboardputscancode'] + SCANCODES[ch], capture_output=True)
            time.sleep(0.04)

print('[1] Sending SSH activation commands to NixOS live console...')
type_text('Vazus_Dev_VM', '\n')
time.sleep(1)
type_text('Vazus_Dev_VM', 'echo root:123 | chpasswd\n')
time.sleep(1)
type_text('Vazus_Dev_VM', 'echo nixos:123 | chpasswd\n')
time.sleep(1)
type_text('Vazus_Dev_VM', 'systemctl start sshd\n')
time.sleep(2)
print('[2] Live system SSH server activated on port 22 (mapped to 127.0.0.1:2222)!')
