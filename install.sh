# Setup WSL on Windows first (PowerShell):
#   wsl --install -d Ubuntu-24.04      # reboot if asked, then create a user when it opens

cd /Unicompta
sudo apt update
# python3-gnucash is no longer needed: gnucash_utils.py is pure python (lxml). python3-tk also serves matplotlib (TkAgg)
sudo apt install -y --no-install-recommends python3-venv python3-pip libmagic1 python3-tk poppler-utils git
sudo python3 -m venv venv
sudo ./venv/bin/pip install pymupdf Pillow copykitten lxml matplotlib ollama pdf2image python-magic
./venv/bin/python -c "import fitz, lxml, matplotlib, tkinter; print('ok')"   # sanity check

# Optional: bundle Ollama for PDF auto-fill (adds ~3 GB to the image)
curl -fsSL https://ollama.com/install.sh | sh
(ollama serve &) ; sleep 5 ; ollama pull gemma3:4b

# Cleanup before export
sudo rm -rf /Unicompta/.git                      # the Unicompta repo history isn't needed (the data repo is separate)
sudo rm -f /Unicompta/config                     # created on the user's machine (or asked by the app at first launch)
sudo apt autoremove -y && sudo apt clean
sudo rm -rf /var/lib/apt/lists/* /root/.cache /home/*/.cache

# Export the image (PowerShell):
#   wsl --export Ubuntu-24.04 Unicompta.tar