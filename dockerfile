FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r https://raw.githubusercontent.com/NekoUwUGamerfnf/Nutone-Api-Discord-Bot/refs/heads/main/requirements.txt

CMD ["python3", "nutone.py"]