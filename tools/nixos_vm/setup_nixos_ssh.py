import paramiko
import subprocess
import time

key_path = r'C:\vazus\tools\nixos_vm_key'
key = paramiko.RSAKey.generate(2048)
key.write_private_key_file(key_path)
pub_key_str = f'{key.get_name()} {key.get_base64()} vazus_agent'
print('Generated public key:', pub_key_str)

SCANCODES = {
    'a': ['1e', '9e'], 'b': ['30', 'b0'], 'c': ['2e', 'ae'], 'd': ['20', 'a0'], 'e': ['12', '92'],
    'f': ['21', 'a1'], 'g': ['22', 'a2'], 'h': ['23', 'a3'], 'i': ['17', '97'], 'j': ['24', 'a4'],
    'k': ['25', 'a5'], 'l': ['26', 'a6'], 'm': ['32', 'b2'], 'n': ['31', 'b1'], 'o': ['18', '98'],
    'p': ['19', '99'], 'q': ['10', '90'], 'r': ['13', '93'], 's': ['1f', '9f'], 't': ['14', '94'],
    'u': ['16', '96'], 'v': ['2f', 'af'], 'w': ['11', '91'], 'x': ['2d', 'ad'], 'y': ['15', '95'],
    'z': ['2c', 'ac'], 'A': ['2a', '1e', '9e', 'aa'], 'B': ['2a', '30', 'b0', 'aa'], 'C': ['2a', '2e', 'ae', 'aa'],
    'D': ['2a', '20', 'a0', 'aa'], 'E': ['2a', '12', '92', 'aa'], 'F': ['2a', '21', 'a1', 'aa'], 'G': ['2a', '22', 'a2', 'aa'],
    'H': ['2a', '23', 'a3', 'aa'], 'I': ['2a', '17', '97', 'aa'], 'J': ['2a', '24', 'a4', 'aa'], 'K': ['2a', '25', 'a5', 'aa'],
    'L': ['2a', '26', 'a6', 'aa'], 'M': ['2a', '32', 'b2', 'aa'], 'N': ['2a', '31', 'b1', 'aa'], 'O': ['2a', '18', '98', 'aa'],
    'P': ['2a', '19', '99', 'aa'], 'Q': ['2a', '10', '90', 'aa'], 'R': ['2a', '13', '93', 'aa'], 'S': ['2a', '1f', '9f', 'aa'],
    'T': ['2a', '14', '94', 'aa'], 'U': ['2a', '16', '96', 'aa'], 'V': ['2a', '2f', 'af', 'aa'], 'W': ['2a', '11', '91', 'aa'],
    'X': ['2a', '2d', 'ad', 'aa'], 'Y': ['2a', '15', '95', 'aa'], 'Z': ['2a', '2c', 'ac', 'aa'],
    '1': ['02', '82'], '2': ['03', '83'], '3': ['04', '84'], '4': ['05', '85'], '5': ['06', '86'],
    '6': ['07', '87'], '7': ['08', '88'], '8': ['09', '89'], '9': ['0a', '8a'], '0': ['0b', '8b'],
    ' ': ['39', 'b9'], '\n': ['1c', '9c'], '-': ['0c', '8c'], '=': ['0d', '8d'], '+': ['2a', '0d', '8d', 'aa'],
    ':': ['2a', '27', 'a7', 'aa'], ';': ['27', 'a7'], '/': ['35', 'b5'], '.': ['34', 'b4'],
    '|': ['2a', '2b', 'ab', 'aa'], '\"': ['2a', '28', 'a8', 'aa'], '\'': ['28', 'a8'], '_': ['2a', '0c', '8c', 'aa'],
    '>': ['2a', '34', 'b4', 'aa'], '<': ['2a', '33', 'b3', 'aa'], '$': ['2a', '05', '85', 'aa'], '~': ['2a', '29', 'a9', 'aa']
}

def type_text(vm_name, text):
    vbox = r'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
    for ch in text:
        if ch in SCANCODES:
            subprocess.run([vbox, 'controlvm', vm_name, 'keyboardputscancode'] + SCANCODES[ch], capture_output=True)
            time.sleep(0.02)

print('Typing into console...')
type_text('Vazus_Dev_VM', '\n')
time.sleep(0.5)
type_text('Vazus_Dev_VM', 'mkdir -p ~/.ssh; chmod 700 ~/.ssh\n')
time.sleep(0.5)
type_text('Vazus_Dev_VM', f'echo \"{pub_key_str}\" >> ~/.ssh/authorized_keys\n')
time.sleep(0.5)
type_text('Vazus_Dev_VM', 'chmod 600 ~/.ssh/authorized_keys; systemctl start sshd\n')
time.sleep(2)

print('Testing SSH connection...')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connected = False
for user in ['root', 'nixos']:
    try:
        print(f'Trying SSH as {user}...')
        ssh.connect('127.0.0.1', port=2222, username=user, key_filename=key_path, timeout=5)
        print(f'SUCCESS! CONNECTED AS {user}!')
        stdin, stdout, stderr = ssh.exec_command('uname -a; lsblk')
        print(stdout.read().decode())
        ssh.close()
        connected = True
        break
    except Exception as e:
        print(f'Failed as {user}: {e}')
