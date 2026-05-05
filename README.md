# Unicompta
pip install tkinterdnd2
sudo apt-get install python3-gnucash

# Save your current packages first

source .../bin/activate
pip freeze > requirements.txt

# Recreate with system access

deactivate
python3 -m venv --system-site-packages .../venv

# Reinstall your packages

pip install -r requirements.txt
