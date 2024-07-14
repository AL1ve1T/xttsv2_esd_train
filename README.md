conda env create --file env.yml

pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

cd ./TTS

pip3 install -e .