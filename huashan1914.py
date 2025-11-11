import urllib.request as req
import bs4 as bs
import ssl
import os
import json
import time
import re
from urllib.parse import quote, urlsplit, urlunsplit
import csv

# ======================================================
# 建立不驗證 SSL 憑證的 context
# ======================================================
context = ssl._create_unverified_context()

base_url = "https://www.huashan1914.com/w/huashan1914/exhibition"

# ======================================================
# 建立 Downloads 資料夾
# ======================================================
downloads_folder = os.path.join(os.getcwd(), "Downloads")
poster_folder = os.path.join(downloads_folder, "images")
os.makedirs(downloads_folder, exist_ok=True)
os.makedirs(poster_folder, exist_ok=True)

# ======================================================
# Step 1 找出總頁數
# ======================================================
response = req.urlopen(base_url, context=context)
content = response.read()
html = bs.BeautifulSoup(content, "html.parser")

total_page_span = html.find("span", {"class": "totalPage"})
if total_page_span:
    nums = total_page_span.find_all("span", {"class": "num"})
    total_pages = int(nums[-1].get_text(strip=True)) if nums else 1
else:
    total_pages = 1

print(f"總共有 {total_pages} 頁")

# ======================================================
# Step 2 開始逐頁爬取展覽資訊
# ======================================================
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
            title_tag = html_inner.find("div", {"class": "article-title page"})
            title = title_tag.get_text(strip=True) if title_tag else ""
            safe_title = re.sub(r'[\\/*?:"<>|∣]', "_", title).strip()

            # ===== 展覽日期與時間 =====
            date_text, time_text, time_detail_text = "", "", ""
            date_block = html_inner.find("div", class_=lambda c: c and "card-datetime" in c)
            if date_block:
                date_parts = date_block.find_all("div", {"class": "card-date"})
                if len(date_parts) >= 2:
                    date_text = f"{date_parts[0].get_text(strip=True)} ~ {date_parts[1].get_text(strip=True)}"
                elif len(date_parts) == 1:
                    date_text = date_parts[0].get_text(strip=True)
                time_tag = date_block.find("div", {"class": "card-time"})
                if time_tag:
                    time_text = time_tag.get_text(strip=True)
                next_block = date_block.find_next_sibling()
                if next_block and next_block.name == "div" and "card-text-info" in (next_block.get("class") or []):
                    time_detail_text = next_block.get_text(strip=True)

            # ===== 展覽類型 =====
            type_text = ""
            type_block = html_inner.find("div", {"id": "divChips"})
            if type_block:
                chip_spans = type_block.find_all("span", {"class": "chip-name"})
                type_text = "/".join(span.get_text(strip=True) for span in chip_spans)

            # ===== 主辦單位 =====
            organizer_text = ""
            organizer_block = html_inner.find("div", {"class": "organizer"})
            if organizer_block:
                organizers = organizer_block.find_all("div", {"class": "inlineDiv"})
                organizer_text = "/".join(div.get_text(strip=True) for div in organizers)

            # ===== 活動地點 =====
            location_text, location_url = "", ""
            location_block = html_inner.find("div", {"class": "address"})
            if location_block:
                a_tags = location_block.find_all("a", {"class": "openMap"})
                if a_tags:
                    locations, urls = [], []
                    for a_tag in a_tags:
                        text = a_tag.get_text(strip=True)
                        href = a_tag.get("href", "")
                        if href.startswith("/"):
                            href = "https://www.huashan1914.com" + href
                        if text:
                            locations.append(text)
                        if href:
                            urls.append(href)
                    location_text = " / ".join(locations)
                    location_url = " / ".join(urls)

            # ===== 展覽介紹 =====
            desc_blocks = html_inner.find_all("div", class_="card-text-info")
            desc_texts = []
            for block in desc_blocks:
                text = block.get_text(strip=True)
                if not text:
                    continue
                if any(x in text for x in [":", "AM", "PM", "～", "~"]) and len(text) < 60:
                    continue
                prev = block.find_previous_sibling()
                if prev and "card-datetime" in (prev.get("class") or []):
                    continue
                desc_texts.append(text)
            description_text = "\n".join(desc_texts).strip()

            # ===== 展覽圖片（主內容）=====
            poster_urls = []
            poster_files = []

            def normalize_img_url(src: str) -> str:
                s = (src or "").strip()
                if not s:
                    return ""
                if s.startswith("/"):
                    s = "https://media.huashan1914.com" + s
                s_lower = s.lower()
                # 圖片可能來自 huashan1914 或 umaytheater
                if not any(d in s_lower for d in ["huashan1914", "umaytheater"]):
                    return ""
                if not any(ext in s_lower for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                    return ""

                parts = urlsplit(s)
                safe_path = quote(parts.path, safe="/%._-~")
                safe_query = quote(parts.query, safe="=&%._-~")
                return urlunsplit((parts.scheme, parts.netloc, safe_path, safe_query, parts.fragment))

            # 只鎖定主內容的圖：imgWidth-middle / original-size
            # 並且「排除」任何位於 .recommend（相關活動）裡的卡片
            img_blocks = html_inner.select("div.card.shadow-none.imgWidth-middle, div.card.shadow-none.original-size")

            clean_blocks = []
            for block in img_blocks:
                # 如果這個 block 位於 .recommend 區塊裡，跳過
                if block.find_parent("div", class_="recommend"):
                    continue
                clean_blocks.append(block)

            for block in clean_blocks:
                for img in block.find_all("img"):
                    raw = img.get("src", "")
                    url = normalize_img_url(raw)
                    if url:
                        poster_urls.append(url)

            # 去重（保持原順序）
            poster_urls = list(dict.fromkeys(poster_urls))

            # 下載圖片
            for url in poster_urls:
                base_name = os.path.basename(urlsplit(url).path)
                filename = f"{safe_title}_{base_name}"
                filepath = os.path.join(poster_folder, filename)
                poster_files.append(filename)

                if os.path.exists(filepath):
                    print(f"[SKIP] 已存在：{filename}")
                    continue

                try:
                    request = req.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with req.urlopen(request, context=context) as resp, open(filepath, "wb") as out:
                        out.write(resp.read())
                    print(f"[OK] 已下載：{filename}")
                except Exception as e:
                    print(f"[ERR] 無法下載圖片：{url} -> {e}")

            # ===== 聯絡資訊 =====
            contact_text = ""
            contact_block = html_inner.find("div", {"class": "article-contact"})
            if contact_block:
                contact_text = contact_block.get_text(strip=True)

            # ===== 官方網站與行事曆等 =====
            official_ig = ""
            official_website = ""
            calendar_links = []
            official_fb = ""

            btn_blocks = html_inner.find_all("div", class_="card-btn")
            for div in btn_blocks:
                a_tag = div.find("a")
                if not a_tag:
                    continue
                text = a_tag.get_text(strip=True)
                href = a_tag.get("href", "").strip()
                if "官方粉絲團(IG)" in text:
                    official_ig = href
                elif "活動官網" in text:
                    official_website = href

            calendar_base = "https://www.huashan1914.com/Event/Calendar"
            calendar_block = html_inner.find("div", {"class": "card-calendar"})
            if calendar_block:
                for a in calendar_block.find_all("a"):
                    link_text = a.get_text(strip=True)
                    href = a.get("href", "").strip()
                    calendar_links.append({"text": link_text, "url": href})

            if calendar_links and all(link["url"].startswith("javascript") for link in calendar_links):
                location_encoded = quote(location_text or "")
                title_encoded = quote(title)
                calendar_links = [
                    {"text": "Google Calendar", "url": f"{calendar_base}?CalendarType=Google&Title={title_encoded}&Location={location_encoded}"},
                    {"text": "iCal ( iOS )", "url": f"{calendar_base}?CalendarType=iCal&Title={title_encoded}&Location={location_encoded}"},
                    {"text": "Outlook", "url": f"{calendar_base}?CalendarType=Outlook&Title={title_encoded}&Location={location_encoded}"}
                ]

            # ===== FB =====
            fb_block = html_inner.find("div", {"class": "card-box border"}, onclick=True)
            if fb_block:
                onclick_value = fb_block.get("onclick", "")
                match = re.search(r"window\.open\('([^']+)'\)", onclick_value)
                if match:
                    official_fb = match.group(1)

            # ======= 印出結果 =======
            print(f"展覽名稱：{title}")
            print(f"展覽日期：{date_text}")
            print(f"展覽圖片連結：{poster_urls}")
            print(f"展覽圖片檔名：{poster_files}")

            # ======= 加入清單 =======
            exhibitions.append({
                "title": title,
                "date": date_text,
                "time": time_text,
                "time_detail": time_detail_text,
                "type": type_text,
                "organizer": organizer_text,
                "location": location_text,
                "location_url": location_url,
                "description": description_text,
                "contact_info": contact_text,
                "official_ig": official_ig,
                "official_website": official_website,
                "calendar_links": calendar_links,
                "official_fb": official_fb,
                "poster_urls": poster_urls,
                "poster_files": poster_files,
                "url": detail_url
            })

            time.sleep(0.5)

        except Exception as e:
            print(f"無法讀取 {detail_url}：{e}")

# ======================================================
# Step 3：Footer 輸出
# ======================================================
footer_info = {}
footer_left = html.find("div", {"class": "footer-left-side"})

if footer_left:
    sections = footer_left.find_all("div", recursive=False)
    for sec in sections:
        title_div = sec.find("div", class_="title")
        if not title_div:
            continue
        title_text = title_div.get_text(strip=True)
        li_list = sec.find_all("li")

        # 「如何來華山」
        if "如何來華山" in title_text:
            address = ""
            open_time = ""
            links = []
            if len(li_list) >= 1:
                address = li_list[0].get_text(strip=True).replace("園區地址：", "")
            if len(li_list) >= 2:
                open_time = li_list[1].get_text(strip=True).replace("開放時間：", "")
            if len(li_list) >= 3:
                for a in li_list[2].find_all("a"):
                    text = a.get_text(strip=True)
                    href = a.get("href", "")
                    if href and not href.startswith("http"):
                        href = "https://www.huashan1914.com/w/huashan1914/" + href.lstrip("/")
                    links.append({"text": text, "url": href})
            footer_info["how_to_come"] = {
                "address": address,
                "open_time": open_time,
                "links": links
            }

        # 「洽公(場地租借)聯繫」
        elif "洽公" in title_text:
            phone = fax = office_hours = ""
            if len(li_list) >= 1:
                phone = li_list[0].get_text(strip=True).replace("電話：", "")
            if len(li_list) >= 2:
                fax = li_list[1].get_text(strip=True).replace("傳真：", "")
            if len(li_list) >= 3:
                office_hours = li_list[2].get_text(strip=True)
            footer_info["rent_contact"] = {
                "phone": phone,
                "fax": fax,
                "office_hours": office_hours
            }

        # 「園區服務聯繫」
        elif "園區服務聯繫" in title_text:
            phone = fax = service_hours = ""
            if len(li_list) >= 1:
                phone = li_list[0].get_text(strip=True).replace("電話：", "")
            if len(li_list) >= 2:
                fax = li_list[1].get_text(strip=True).replace("傳真：", "")
            if len(li_list) >= 3:
                service_hours = li_list[2].get_text(strip=True)
            footer_info["service_contact"] = {
                "phone": phone,
                "fax": fax,
                "service_hours": service_hours
            }

# ======================================================
# Step 4：JSON 輸出
# ======================================================
output_data = {
    "exhibitions": exhibitions,
    "footer_info": footer_info
}

output_path = os.path.join(downloads_folder, "huashan_exhibitions_detail.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print(f"\n已完成所有資料爬取，結果輸出至：{output_path}")

# ======================================================
# Step 5：CSV 輸出
# ======================================================
csv_output_path = os.path.join(downloads_folder, "huashan_exhibitions_detail.csv")

# 準備要輸出的欄位（與 JSON 一致）
csv_fields = [
    "title", "date", "time", "time_detail",
    "type", "organizer", "location", "location_url",
    "description", "contact_info",
    "official_ig", "official_website", "official_fb",
    "poster_urls", "poster_files", "url"
]

# 寫出 CSV
with open(csv_output_path, "w", newline="", encoding="utf-8-sig") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=csv_fields)
    writer.writeheader()
    for ex in exhibitions:
        # 轉換列表型欄位為字串（避免 list 寫入時出錯）
        row = {k: (", ".join(v) if isinstance(v, list) else v) for k, v in ex.items() if k in csv_fields}
        writer.writerow(row)

print(f"已同時輸出 CSV 檔案：{csv_output_path}")