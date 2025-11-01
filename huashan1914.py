import urllib.request as req
import bs4 as bs
import ssl
import os
import json
import time

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
exhibitions = []

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

        detail_url = "https://www.huashan1914.com" + a_tag["href"]

        print("-" * 80)
        print(f"進入內層頁面：{detail_url}")

        try:
            response_inner = req.urlopen(detail_url, context=context)
            content_inner = response_inner.read()
            html_inner = bs.BeautifulSoup(content_inner, "html.parser")

            # ======= 內頁資料擷取 =======

            # 展覽名稱
            title_tag = html_inner.find("div", {"class": "article-title page"})
            title = title_tag.get_text(strip=True) if title_tag else ""

            # 展覽日期與時間
            date_block = html_inner.find("div", {"class": "card-datetime multiple"})
            if date_block:
                date_parts = date_block.find_all("div", {"class": "card-date"})
                time_tag = date_block.find("div", {"class": "card-time"})
                if len(date_parts) >= 2:
                    date_text = (
                        date_parts[0].get_text(strip=True) + " ~ " + date_parts[1].get_text(strip=True)
                    )
                elif len(date_parts) == 1:
                    date_text = date_parts[0].get_text(strip=True)
                else:
                    date_text = ""
                time_text = time_tag.get_text(strip=True) if time_tag else ""
            else:
                date_text = ""
                time_text = ""

            # 展覽類型
            type_block = html_inner.find("div", {"id": "divChips"})
            type_text = ""
            if type_block:
                chip_spans = type_block.find_all("span", {"class": "chip-name"})
                type_text = "/".join(span.get_text(strip=True) for span in chip_spans)

            # 主辦單位
            organizer_block = html_inner.find("div", {"class": "organizer"})
            organizer_text = ""
            if organizer_block:
                organizers = organizer_block.find_all("div", {"class": "inlineDiv"})
                organizer_text = "/".join(div.get_text(strip=True) for div in organizers)

            # 活動地點
            location_block = html_inner.find("div", {"class": "address"})
            location_text = ""
            location_url = ""
            if location_block:
                a_tag_loc = location_block.find("a", {"class": "openMap"})
                if a_tag_loc:
                    location_text = a_tag_loc.get_text(strip=True)
                    location_url = "https://www.huashan1914.com" + a_tag_loc.get("href", "")

            # 展覽介紹
            description_block = html_inner.find("div", {"class": "card-text-info"})
            description_text = ""
            if description_block:
                # 將所有段落文字組成一段
                ps = description_block.find_all("p")
                if ps:
                    description_text = "\n".join(p.get_text(strip=True) for p in ps)
                else:
                    description_text = description_block.get_text(strip=True)

            # 聯絡資訊
            contact_block = html_inner.find("div", {"class": "article-contact"})
            contact_text = ""
            if contact_block:
                # 聯絡資訊可能在 <div> 或 <li> 中
                contact_text = contact_block.get_text(strip=True)

            # ======= 結果印出 =======
            print(f"展覽名稱：{title}")
            print(f"展覽日期：{date_text}")
            print(f"開放時間：{time_text}")
            print(f"展覽類型：{type_text}")
            print(f"主辦單位：{organizer_text}")
            print(f"活動地點：{location_text}")
            print(f"活動地點的位置連結：{location_url}")
            print(f"展覽介紹：{description_text}")
            print(f"聯絡資訊：{contact_text}")

            # ======= 加入清單 =======
            exhibitions.append({
                "title": title,
                "date": date_text,
                "time": time_text,
                "type": type_text,
                "organizer": organizer_text,
                "location": location_text,
                "location_url": location_url,
                "description": description_text,
                "contact_info": contact_text,
                "url": detail_url
            })

            time.sleep(0.5)  # 防止過於頻繁請求

        except Exception as e:
            print(f"無法讀取 {detail_url}：{e}")

# Step 3 儲存成 JSON 檔
output_path = os.path.join(downloads_folder, "huashan_exhibitions_detail.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(exhibitions, f, ensure_ascii=False, indent=2)

print(f"\n已完成所有內層展覽資料爬取，結果輸出至：{output_path}")