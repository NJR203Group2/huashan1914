import urllib.request as req
import bs4 as bs
import ssl
import os
import json

# 建立不驗證 SSL 憑證的 context
context = ssl._create_unverified_context()

base_url = "https://www.huashan1914.com/w/huashan1914/exhibition"

# 建立 Downloads 資料夾
downloads_folder = os.path.join(os.getcwd(), "Downloads")
if not os.path.exists(downloads_folder):
    os.makedirs(downloads_folder)

# 先抓第一頁來判斷總頁數
response = req.urlopen(base_url, context=context)
content = response.read()
html = bs.BeautifulSoup(content, "html.parser")

# Step 1 找出總頁數
total_page_span = html.find("span", {"class": "totalPage"})
if total_page_span:
    nums = total_page_span.find_all("span", {"class": "num"})
    total_pages = int(nums[-1].get_text(strip=True)) if nums else 1
else:
    total_pages = 1

print(f"總共有 {total_pages} 頁")

# Step 2 開始逐頁爬取
exhibitions = []  # ← 新增這一行，開始收集所有展覽資料

for page in range(1, total_pages + 1):
    page_url = f"{base_url}?index={page}"
    print(f"\n正在爬取第 {page} 頁：{page_url}")

    response = req.urlopen(page_url, context=context)
    content = response.read()
    html = bs.BeautifulSoup(content, "html.parser")

    items = html.find_all("li", {"class": "item-static"})
    for li in items:
        a_tag = li.find("a")
        if not a_tag or "href" not in a_tag.attrs:
            continue

        # 各欄位的抽取
        name_tag = li.find("div", {"class": "card-text-name"})
        date_tag = li.find("div", {"class": "event-date"})
        time_tag = li.find("div", {"class": "event-time"})
        type_tag = li.find("div", {"class": "event-list-type"})

        title = name_tag.get_text(strip=True) if name_tag else ""
        date_text = date_tag.get_text(strip=True) if date_tag else ""
        time_text = time_tag.get_text(strip=True) if time_tag else ""
        type_text = ""
        if type_tag:
            span_list = type_tag.find_all("span")
            type_text = "/".join(span.get_text(strip=True) for span in span_list)

        link = "https://www.huashan1914.com" + a_tag["href"]

        # 印出到終端機
        print("-" * 80)
        print(f"展覽名稱：{title}")
        print(f"展覽日期：{date_text}")
        print(f"開放時間：{time_text}")
        print(f"展覽類型：{type_text}")
        print(f"展覽連結：{link}")

        # 加入清單以便輸出成 JSON
        exhibitions.append({
            "title": title,
            "date": date_text,
            "time": time_text,
            "type": type_text,
            "url": link
        })

# Step 3 儲存成 JSON 檔
output_path = os.path.join(downloads_folder, "huashan_exhibitions.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(exhibitions, f, ensure_ascii=False, indent=2)

print(f"\n已完成爬取，結果輸出至：{output_path}")