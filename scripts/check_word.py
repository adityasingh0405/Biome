import subprocess

ps_script = """
$word = New-Object -ComObject Word.Application
Write-Host "Word Version:" $word.Version
$word.Quit()
"""

res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
