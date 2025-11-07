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
os.makedirs(downloads_folder, exist_ok=True)

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

# Step 2 開始逐頁爬取展覽資訊
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
            date_text, time_text, time_detail_text = "", "", ""
            date_block = html_inner.find("div", class_=lambda c: c and "card-datetime" in c)

            if date_block:
                # 日期
                date_parts = date_block.find_all("div", {"class": "card-date"})
                if len(date_parts) >= 2:
                    date_text = f"{date_parts[0].get_text(strip=True)} ~ {date_parts[1].get_text(strip=True)}"
                elif len(date_parts) == 1:
                    date_text = date_parts[0].get_text(strip=True)

                # 主要時間
                time_tag = date_block.find("div", {"class": "card-time"})
                if time_tag:
                    time_text = time_tag.get_text(strip=True)

                # 活動時間說明（緊接在 card-datetime 後）
                next_block = date_block.find_next_sibling()
                if next_block and next_block.name == "div" and "card-text-info" in (next_block.get("class") or []):
                    time_detail_text = next_block.get_text(strip=True)

            # 展覽類型
            type_block = html_inner.find("div", {"id": "divChips"})
            type_text = ""
            if type_block:
                chip_spans = type_block.find_all("span", {"class": "chip-name"})
                type_text = "/".join(span.get_text(strip=True) for span in chip_spans)

            # 主辦單位
            organizer_text = ""
            organizer_block = html_inner.find("div", {"class": "organizer"})
            if organizer_block:
                organizers = organizer_block.find_all("div", {"class": "inlineDiv"})
                organizer_text = "/".join(div.get_text(strip=True) for div in organizers)

            # ===== 活動地點（location & location_url）=====
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

            # ===== 聯絡資訊 =====
            contact_text = ""
            contact_block = html_inner.find("div", {"class": "article-contact"})
            if contact_block:
                contact_text = contact_block.get_text(strip=True)

            # ===== 官方粉絲團(IG)、活動官網、加入行事曆、官方粉絲團(FB) =====
            official_ig = ""
            official_website = ""
            calendar_links = []
            official_fb = ""

            # --- IG 與活動官網 ---
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

            # --- 加入你的行事曆 ---
            calendar_block = html_inner.find("div", {"class": "card-calendar"})
            if calendar_block:
                a_tags = calendar_block.find_all("a")
                for a in a_tags:
                    link_text = a.get_text(strip=True)
                    href = a.get("href", "")
                    calendar_links.append({"text": link_text, "url": href})

            # --- 官方粉絲團(FB) ---
            fb_block = html_inner.find("div", {"class": "card-box border"}, onclick=True)
            if fb_block:
                onclick_value = fb_block.get("onclick", "")
                if "facebook.com" in onclick_value:
                    # 從 onclick="window.open('https://www.facebook.com/...')" 中取出 URL
                    import re
                    match = re.search(r"window\.open\('([^']+)'\)", onclick_value)
                    if match:
                        official_fb = match.group(1)

            # ======= 印出結果 =======
            print(f"展覽名稱：{title}")
            print(f"展覽日期：{date_text}")
            print(f"開放時間：{time_text}")
            print(f"活動時間說明：{time_detail_text}")
            print(f"展覽類型：{type_text}")
            print(f"主辦單位：{organizer_text}")
            print(f"活動地點：{location_text}")
            print(f"活動地點位置連結：{location_url}")
            print(f"展覽介紹：{description_text}")
            print(f"聯絡資訊：{contact_text}")
            print(f"官方粉絲團(IG)：{official_ig}")
            print(f"活動官網：{official_website}")
            print(f"加入你的行事曆：{calendar_links}")
            print(f"官方粉絲團(FB)：{official_fb}")

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
                "url": detail_url
            })

            time.sleep(0.5)

        except Exception as e:
            print(f"無法讀取 {detail_url}：{e}")

# ===== Step 3: 抓取網站底部 footer 資訊 =====
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

# Step 4 儲存 JSON
output_data = {
    "exhibitions": exhibitions,
    "footer_info": footer_info
}

output_path = os.path.join(downloads_folder, "huashan_exhibitions_detail.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print(f"\n已完成所有資料爬取，結果輸出至：{output_path}")