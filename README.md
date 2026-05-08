# Installs

### Launch the following commands from a bash terminal (in vscode terminal for exmaple)

```bash
pip install tkinterdnd2
pip install pdf2image Pillow
sudo apt-get install python3-gnucash

# Save your current packages first

source .../bin/activate
pip freeze > requirements.txt

# Recreate with system access

deactivate
python3 -m venv --system-site-packages .../venv

# Reinstall your packages

pip install -r requirements.txt
```

# Setting parameters

### Go into the * **config** * file and paste the path to your UPSecretrariat folder

# Running the code

### launch the main.py and use the GUI
