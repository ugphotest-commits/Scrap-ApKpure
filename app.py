import re
import cloudscraper
import requests
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
app = Flask(__name__)
DEFAULT_URL = "https://apkpure.com/free-fire-app/com.dts.freefireth/download"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7,ar;q=0.6",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "Priority": "u=0, i",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://apkpure.com/free-fire-app/com.dts.freefireth",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Sec-Ch-Ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Ch-Ua-Platform-Version": '"10.0.0"',
    "Sec-Ch-Ua-Arch": '"x86"',
    "Sec-Ch-Ua-Bitness": '"64"',
    "Sec-Ch-Ua-Full-Version": '"150.0.0.0"',
    "Sec-Ch-Ua-Full-Version-List": '"Not;A=Brand";v="8", "Chromium";v="150.0.0.0", "Google Chrome";v="150.0.0.0"',
    "Referrer-Policy": "no-referrer-when-downgrade",
}
COOKIE_STRING = (
    "_apk_uid=NCmAeJd7h14tGRA6A30fArMdhfbZ3TfF; "
    "_qimei=tHN0Q7p02ja74jZp8S7ZENCtPYCMzwkM; "
    "_user_tag=j%3A%7B%22language%22%3A%22en%22%2C%22source_language%22%3A%22fr-FR%22%2C%22country%22%3A%22FR%22%7D; "
    "apkpure_euid=; "
    "m1=20644; "
    "m2=ec9cddf7fa2e8f47c4ae4ed27619a338;"
)
def fetch_html(url: str) -> str:
    scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
    headers = HEADERS.copy()
    headers.pop("Accept-Encoding", None)
    headers["Cookie"] = COOKIE_STRING
    response = scraper.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.text
def extract_info(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    data = {"md5": None, "version": None, "version_code": None}

    sig_label = soup.find("span", class_="label", string=re.compile(r"Signature", re.I))
    if sig_label:
        value_span = sig_label.find_next("span", class_="value")
        if value_span:
            data["md5"] = value_span.get_text(strip=True)
    if not data["md5"]:
        m = re.search(r'Signature</span>\s*<span[^>]*class="value"[^>]*>([0-9a-fA-F]+)</span>', html)
        if m:
            data["md5"] = m.group(1)
    one_line = soup.find("strong", class_="one-line")
    if one_line:
        text = one_line.get_text(strip=True)
        m = re.search(r"(\d+\.\d+(?:\.\d+)?)", text)
        if m:
            data["version"] = m.group(1)
    if not data["version"]:
        m = re.search(r'<strong class="one-line">.*?(\d+\.\d+(?:\.\d+)?)\s*</strong>', html)
        if m:
            data["version"] = m.group(1)
    additional = soup.find("span", class_="additional-info one-line")
    if not additional:
        additional = soup.find("span", class_=lambda c: c and "additional-info" in c and "one-line" in c)
    if additional:
        text = additional.get_text(strip=True)
        m = re.search(r"\((\d+)\)", text)
        if m:
            data["version_code"] = m.group(1)
    if not data["version_code"]:
        m = re.search(r'additional-info[^"]*"[^>]*>\s*\((\d+)\)', html)
        if m:
            data["version_code"] = m.group(1)
    return data
def fetch_remote_version(version: str) -> dict:
    url = (f"https://version.ggwhitehawk.com/live/ver.php?version={version}&lang=fr&device=android&channel=android&appstore=googleplay&region=ME&release_version=OB54&whitelist_version=1.7.0&whitelist_sp_version=1.0.0&device_name=OnePlus%20NE2211&device_CPU=ARMv7%20VFPv3%20NEON&device_GPU=Adreno%20%28TM%29%20540&device_mem=3940")
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    return {
        "remote_version": data.get("remote_version"),
        "server_url": data.get("server_url"),
        "latest_release_version": data.get("latest_release_version"),
    }
@app.route("/info", methods=["GET"])
def info():
    url = request.args.get("url", DEFAULT_URL)
    try:
        html = fetch_html(url)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch page: {e}"}), 502
    data = extract_info(html)
    if data.get("version"):
        try:
            remote = fetch_remote_version(data["version"])
            data.update(remote)
        except Exception as e:
            data["remote_error"] = f"Failed to fetch remote version: {e}"
    missing = [k for k, v in data.items() if v is None]
    if missing:
        data["warning"] = f"Could not extract: {', '.join(missing)} from the page."
    data["source"] = "Telegram: @bottmk"
    return jsonify(data)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
