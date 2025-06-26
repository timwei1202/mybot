# ==== 全域設定 ====
import requests
import time
import asyncio
from datetime import datetime, timedelta
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
import os
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

SEARCH_INTERVAL = 1  # 每輪搜尋間隔（秒）
MAX_SEARCH_ROUNDS = 666  # 最多搜尋輪次  # 最多搜尋輪次

# 設置日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class LotteryCrawler:
    def __init__(self):
        # 代理IP列表
        self.proxy_list = [
            "110.43.221.121:7088",
            "112.19.241.37:19999"
        ]

        # 福彩3D網站
        self.fc3d_url = "https://www.cwl.gov.cn/"

    def setup_driver_with_proxy(self, proxy_ip):
        """設置使用代理的無頭瀏覽器"""
        chrome_options = Options()

        # 基本設置
        chrome_options.add_argument(f'--proxy-server=http://{proxy_ip}')
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

        # 無頭模式設置
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3")  # 禁用日誌

        # 實驗性設置
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(20)
            driver.implicitly_wait(10)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return driver
        except Exception as e:
            logger.error(f"創建驅動器失敗: {e}")
            return None

    def setup_basic_driver(self):
        """設置基本無頭瀏覽器（不使用代理，用於福彩3D）"""
        chrome_options = Options()

        # 基本設置
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

        # 無頭模式設置
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3")  # 禁用日誌

        # 實驗性設置
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(20)
            driver.implicitly_wait(10)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return driver
        except Exception as e:
            logger.error(f"創建基本驅動器失敗: {e}")
            return None

    def get_working_driver(self):
        """獲取可用的驅動器"""
        for i, proxy_ip in enumerate(self.proxy_list):
            if proxy_ip == "請替換為你的第二個代理IP:端口":
                continue

            logger.info(f"嘗試代理 {i + 1}: {proxy_ip}")
            driver = self.setup_driver_with_proxy(proxy_ip)
            if driver is None:
                continue

            try:
                # 測試連接
                driver.get("https://www.lottery.gov.cn")
                time.sleep(3)

                if "lottery" in driver.current_url.lower():
                    logger.info(f"代理 {proxy_ip} 連接成功")
                    return driver
                else:
                    logger.warning(f"代理 {proxy_ip} 連接失敗 - URL不正確")
                    driver.quit()

            except Exception as e:
                logger.error(f"代理 {proxy_ip} 測試失敗: {e}")
                try:
                    driver.quit()
                except:
                    pass

        logger.error("所有代理都無法連接")
        return None

    def get_lottery_result_from_selenium(self, driver, lottery_type, url):
        """使用Selenium獲取彩票結果"""
        try:
            logger.info(f"正在訪問 {lottery_type} URL: {url}")
            driver.get(url)
            time.sleep(5)

            # 等待並切換到iframe
            try:
                iframe = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "iframe"))
                )
                driver.switch_to.frame(iframe)
                logger.info(f"{lottery_type} - 成功切換到iframe")
            except Exception as e:
                logger.error(f"{lottery_type} - 找不到iframe: {e}")
                return None

            # 等待表格載入
            try:
                table = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "table"))
                )
                logger.info(f"{lottery_type} - 成功找到表格")
            except Exception as e:
                logger.error(f"{lottery_type} - 找不到表格: {e}")
                return None

            # 獲取第三行（最新一期數據）
            rows = table.find_elements(By.TAG_NAME, "tr")
            logger.info(f"{lottery_type} - 找到 {len(rows)} 行數據")

            if len(rows) >= 3:
                latest_row = rows[2]  # 第三行是最新數據
                cells = latest_row.find_elements(By.TAG_NAME, "td")
                logger.info(f"{lottery_type} - 最新行有 {len(cells)} 個單元格")

                if len(cells) >= 6:
                    period = cells[0].text.strip()  # 期號
                    date = cells[1].text.strip()  # 開獎日期

                    # 根據彩票類型決定號碼數量
                    if lottery_type == "排列三":
                        num1 = cells[2].text.strip()  # 號碼1
                        num2 = cells[3].text.strip()  # 號碼2
                        num3 = cells[4].text.strip()  # 號碼3
                        numbers = [num1, num2, num3]
                    else:  # 排列五
                        num1 = cells[2].text.strip()  # 號碼1
                        num2 = cells[3].text.strip()  # 號碼2
                        num3 = cells[4].text.strip()  # 號碼3
                        num4 = cells[5].text.strip()  # 號碼4
                        num5 = cells[6].text.strip()  # 號碼5
                        numbers = [num1, num2, num3, num4, num5]

                    logger.info(f"{lottery_type} - 期號: {period}, 日期: {date}, 號碼: {numbers}")

                    # 檢查是否為今日數據
                    if self.is_today(date):
                        return {
                            'type': lottery_type,
                            'issue': period,
                            'numbers': numbers,
                            'date': date,
                            'confirmed': True
                        }
                    else:
                        logger.info(f"{lottery_type} - 非今日數據")
                else:
                    logger.warning(f"{lottery_type} - 單元格數量不足")
            else:
                logger.warning(f"{lottery_type} - 行數不足")

        except Exception as e:
            logger.error(f"獲取{lottery_type}數據時出錯: {e}")
        finally:
            try:
                driver.switch_to.default_content()
            except:
                pass

        return None


    def get_macau_lottery_data(self):
        """透過 API 獲取澳門六合彩開獎資料"""
        url = "http://api.bjjfnet.com/data/opencode/2032"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                json_data = response.json()
                if json_data["code"] == 0 and "data" in json_data:
                    latest = json_data["data"][0]
                    issue = latest["issue"]
                    numbers = latest["openCode"].split(",")
                    date = latest["openTime"].split(" ")[0]
                    if self.is_today(date):
                        logger.info("澳門六合彩資料獲取成功")
                        return {
                            'type': '澳門六合彩',
                            'issue': issue,
                            'numbers': numbers,
                            'date': date,
                            'confirmed': True
                        }
                    else:
                        logger.info(f"澳門六合彩非今日資料（日期: {date}）")
            else:
                logger.error(f"澳門六合彩 API 請求失敗，狀態碼: {response.status_code}")
        except Exception as e:
            logger.error(f"澳門六合彩資料獲取錯誤: {e}")
        return None


    def is_today(self, date_str):
        """檢查是否為今日"""
        try:
            if date_str:
                today = datetime.now().strftime('%Y-%m-%d')
                is_today_data = date_str == today
                logger.info(f"日期檢查: 今日={today}, 開獎日={date_str}, 是否今日={is_today_data}")
                return is_today_data
        except Exception as e:
            logger.error(f"日期檢查錯誤: {e}")
        return False

    
    async def get_pl5_data(self):
        driver = self.get_working_driver()
        if not driver:
            return None
        try:
            return self.get_lottery_result_from_selenium(driver, "排列五", "https://www.lottery.gov.cn/kj/kjlb.html?plw")
        finally:
            driver.quit()

    async def get_pl3_data(self):
        driver = self.get_working_driver()
        if not driver:
            return None
        try:
            return self.get_lottery_result_from_selenium(driver, "排列三", "https://www.lottery.gov.cn/kj/kjlb.html?pls")
        finally:
            driver.quit()

    async def get_fc3d_data(self):
        """獲取福彩3D數據（使用Selenium）"""
        driver = None
        try:
            # 創建基本驅動器（不使用代理）
            driver = self.setup_basic_driver()
            if driver is None:
                logger.error("無法創建福彩3D瀏覽器驅動")
                return None

            logger.info("正在獲取福彩3D數據...")
            driver.get(self.fc3d_url)
            time.sleep(3)

            # 查找福彩3D容器
            fc3d_container = driver.find_element(By.CSS_SELECTOR, ".fc3d_container")

            # 期號文字，例如 "第2025143期"
            issue_text = fc3d_container.find_element(By.CSS_SELECTOR,
                                                     ".lottery_content > div:nth-child(1)").text.strip()
            issue_number = issue_text.replace("第", "").replace("期", "")

            # 號碼列表
            balls = fc3d_container.find_elements(By.CSS_SELECTOR, ".qiu_list .qiu_item_blue")
            numbers = [b.text.strip() for b in balls]

            # 詳細頁面連結（取 href）
            detail_link = fc3d_container.find_element(By.CSS_SELECTOR,
                                                      ".lottery_btn_container a.lottery_btn").get_attribute("href")

            # 開啟詳細頁面抓日期
            driver.get(detail_link)
            time.sleep(2)

            open_date = "未知"
            for tag in ["div", "span"]:
                try:
                    elem = driver.find_element(By.XPATH, f"//{tag}[contains(text(),'202')]")
                    if elem:
                        open_date = elem.text.strip().replace("开奖日期：", "")
                        # 嘗試清理日期格式，確保是 YYYY-MM-DD 格式
                        import re
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', open_date)
                        if date_match:
                            open_date = date_match.group(1)
                        break
                except NoSuchElementException:
                    continue

            # 如果仍未找到日期，嘗試使用今天日期
            if open_date == "未知":
                open_date = datetime.now().strftime('%Y-%m-%d')

            # 檢查是否為今日數據
            if self.is_today(open_date):
                logger.info("福彩3D數據獲取成功")
                return {
                    'type': '福彩3D',
                    'issue': issue_number,
                    'numbers': numbers,
                    'date': open_date,
                    'confirmed': True
                }
            else:
                logger.info(f"福彩3D非今日數據 (開獎日期: {open_date})，不返回結果")
                return None

        except Exception as e:
            logger.error(f"獲取福彩3D數據失敗: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    logger.error(f"關閉福彩3D驅動器失敗: {e}")

    async def get_all_today_results(self):
        """獲取所有今日開獎結果（按固定順序：排列五、排列三、福彩3D）"""
        results = []

        # 先獲取排列五
        pl5_result = await self.get_pl5_data()
        if pl5_result:
            results.append(pl5_result)

        # 再獲取排列三
        pl3_result = await self.get_pl3_data()
        if pl3_result:
            results.append(pl3_result)

        # 最後獲取福彩3D數據
        fc3d_result = await self.get_fc3d_data()
        if fc3d_result:

            if "澳門六合彩" in missing_types:
                try:
                    macau_result = self.crawler.get_macau_lottery_data()
                    if macau_result:
                        collected_results.append(macau_result)
                        logger.info("新獲取: 澳門六合彩")
                except Exception as e:
                    logger.warning(f"澳門六合彩獲取錯誤: {e}")

            results.append(fc3d_result)

        return results


class TelegramLotteryBot:
    def __init__(self):
        self.crawler = LotteryCrawler()
        self.macau_cache = None

    def format_results_message(self, results, missing_types=None, round_num=0, max_rounds=None):
        if max_rounds is None:
            max_rounds = MAX_SEARCH_ROUNDS
        message = "🎯 今日開獎結果：\n"
        if results:
            for result in results:
                status = "✅ 已確認" if result['confirmed'] else "⏳ 未確認"
                message += f"【{result['type']}】 第{result['issue']}期\n"
                message += f"📅 開獎日期: {result['date']}\n"
                message += f"🎲 開獎號碼: {' '.join(result['numbers'])}\n"
                message += f"📋 狀態: {status}\n\n"
        if missing_types:
            message += f"🔍 持續搜尋中: {', '.join(missing_types)}\n"
            message += f"⏱️ 搜尋輪次: {round_num}/{max_rounds} "
        elif not results:
            message = "❌ 暫無今日開獎數據"
        return message

    async def get_lottery_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        message = await context.bot.send_message(chat_id=chat_id, text="🔍 正在查詢今日開獎結果，請稍候...")

        try:
            collected_results = []
            current_round = 0
            total_types = ['排列五', '排列三', '福彩3D', '澳門六合彩']
            self.macau_cache = None

            while current_round < MAX_SEARCH_ROUNDS:
                current_round += 1
                logger.info(f"開始第 {current_round} 輪搜尋")

                found_types = [r['type'] for r in collected_results]
                missing_types = [t for t in total_types if t not in found_types]

                if set(found_types) == set(total_types):
                    final_message = self.format_results_message(collected_results)
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message.message_id, text=final_message)
                    logger.info("所有彩票資訊已獲取完成")
                    return

                result_message = self.format_results_message(collected_results, missing_types, current_round)
                try:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message.message_id, text=result_message)
                except:
                    pass

                pl5_result = pl3_result = fc3d_result = macau_result = None

                if "排列五" in missing_types:
                    try:
                        pl5_result = await asyncio.wait_for(self.crawler.get_pl5_data(), timeout=30)
                    except Exception as e:
                        logger.warning(f"排列五獲取錯誤: {e}")

                if "排列三" in missing_types:
                    try:
                        pl3_result = await asyncio.wait_for(self.crawler.get_pl3_data(), timeout=30)
                    except Exception as e:
                        logger.warning(f"排列三獲取錯誤: {e}")

                if "福彩3D" in missing_types:
                    try:
                        fc3d_result = await asyncio.wait_for(self.crawler.get_fc3d_data(), timeout=20)
                    except Exception as e:
                        logger.warning(f"福彩3D獲取錯誤: {e}")

                if "澳門六合彩" in missing_types:
                    try:
                        if not self.macau_cache:
                            self.macau_cache = self.crawler.get_macau_lottery_data()
                        macau_result = self.macau_cache
                    except Exception as e:
                        logger.warning(f"澳門六合彩獲取錯誤: {e}")

                for result in [pl5_result, pl3_result, fc3d_result, macau_result]:
                    if result and result['type'] not in found_types:
                        collected_results.append(result)
                        logger.info(f"新獲取: {result['type']}")

                await asyncio.sleep(SEARCH_INTERVAL)

            final_message = self.format_results_message(collected_results)
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message.message_id, text=final_message)
            logger.info("搜尋結束")

        except Exception as e:
            logger.error(f"查詢過程出錯: {e}")
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message.message_id, text="❌ 查詢過程發生錯誤，請稍後再試")

        """處理 /getlt 指令"""
        chat_id = update.effective_chat.id
        user_name = update.effective_user.first_name or "用戶"

        # 發送初始訊息
        message = await context.bot.send_message(
            chat_id=chat_id,
            text="🔍 正在查詢今日開獎結果，請稍候..."
        )

        try:

            collected_results = []
            current_round = 0
            total_types = ['排列五', '排列三', '福彩3D', '澳門六合彩']

            while current_round < MAX_SEARCH_ROUNDS:
                current_round += 1

                try:
                    found_types = [r['type'] for r in collected_results]
                    missing_types = [t for t in total_types if t not in found_types]

                    # 更新訊息
                    result_message = self.format_results_message(
                        collected_results, missing_types, current_round, MAX_SEARCH_ROUNDS
                    )
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message.message_id,
                            text=result_message
                        )
                        logger.info(f"第 {current_round} 輪進度訊息已更新")
                    except Exception as e:
                        logger.debug(f"訊息更新失敗（可能內容相同）: {e}")

                    # 只查詢還沒取得的
                    pailie_results = []
                    fc3d_result = None

                    if any(t in missing_types for t in ["排列三", "排列五"]):
                        pailie_results = []
                        try:
                            # 個別抓取
                            if "排列五" in missing_types:
                                try:
                                    pl5_result = await asyncio.wait_for(self.crawler.get_pl5_data(), timeout=15)
                                    if pl5_result:
                                        pailie_results.append(pl5_result)
                                        logger.info("排列五數據獲取成功")
                                except Exception as e:
                                    logger.warning(f"排列五獲取失敗: {e}")

                            if "排列三" in missing_types:
                                try:
                                    pl3_result = await asyncio.wait_for(self.crawler.get_pl3_data(), timeout=15)
                                    if pl3_result:
                                        pailie_results.append(pl3_result)
                                        logger.info("排列三數據獲取成功")
                                except Exception as e:
                                    logger.warning(f"排列三獲取失敗: {e}")

                            logger.info(f"排列數據獲取結果: {len(pailie_results)} 個")

                        except asyncio.TimeoutError:
                            logger.warning("排列數據獲取超時")
                        except Exception as e:
                            logger.error(f"排列數據獲取異常: {e}")

                    new_found = False

                    for result in pailie_results:
                        if result['type'] not in found_types:
                            insert_index = len(collected_results)
                            for i, existing_result in enumerate(collected_results):
                                if total_types.index(result['type']) < total_types.index(existing_result['type']):
                                    insert_index = i
                                    break
                            collected_results.insert(insert_index, result)
                            new_found = True
                            logger.info(f"新獲取: {result['type']}")

                    if fc3d_result and "福彩3D" not in found_types:
                        collected_results.append(fc3d_result)
                        new_found = True
                        logger.info("新獲取: 福彩3D")

                    # 若資料都取得了，終止
                    if set([r['type'] for r in collected_results]) == set(total_types):
                        final_message = self.format_results_message(collected_results)
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message.message_id,
                            text=final_message
                        )
                        logger.info("所有彩票資訊已獲取完成")
                        return

                    if not new_found and current_round < MAX_SEARCH_ROUNDS:
                        await asyncio.sleep(SEARCH_INTERVAL)

                except Exception as e:
                    logger.error(f"搜尋輪次 {current_round} 出錯: {e}")
                    await asyncio.sleep(3)
                    continue

            # 超過輪次結束
            final_message = self.format_results_message(collected_results)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message.message_id,
                text=final_message
            )
            logger.info("搜尋完成")

        except Exception as e:
            logger.error(f"查詢彩票結果時發生錯誤: {e}")
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message.message_id,
                text="❌ 查詢過程中發生錯誤，請稍後再試"
            )

    def run_bot(self, token: str):
        """運行機器人"""
        # 創建應用程式
        application = Application.builder().token(token).build()

        # 添加指令處理器
        application.add_handler(CommandHandler("getlt", self.get_lottery_command))

        # 運行機器人
        print("🤖 Telegram 彩票機器人已啟動...")
        print("📋 可用指令: /getlt")

        application.run_polling()


def main():
    """主函數"""
    # 直接設置 Bot Token（推薦方法）
    bot_token = "7764981691:AAH2Fof3QC5AP6BLDTyJXZvi9ovs5tlHsiQ"  # 請將 YOUR_BOT_TOKEN_HERE 替換為你的實際 Token

    # 也可以從環境變量獲取（可選）
    # bot_token = os.getenv('BOT_TOKEN')

    if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
        print("❌ 錯誤: 請在代碼中設置你的 Bot Token")
        sys.exit(1)

    # 創建並運行機器人
    bot = TelegramLotteryBot()

    try:
        bot.run_bot(bot_token)
    except KeyboardInterrupt:
        print("\n👋 機器人已停止")
    except Exception as e:
        print(f"❌ 機器人運行錯誤: {e}")


if __name__ == "__main__":
    main()