#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import time
import random
import urllib.request
import urllib.parse
from html import unescape
from urllib.error import URLError, HTTPError
import logging
import xml.etree.ElementTree as ET
from datetime import datetime

class NewsHotWordProvider:
    """新聞熱詞提供器 - 支持Yahoo和Google新聞"""
    
    # 常量定義
    YAHOO_NEWS_URL = "https://tw.news.yahoo.com/"
    GOOGLE_NEWS_URL = "https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    GOOGLE_NEWS_WEB_URL = "https://news.google.com/home?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    MAX_NEWS_ITEMS = 15  # 每個來源的最大新聞數量
    TAG = "NewsHotWords"
    
    def __init__(self, data_dir=None):
        """
        初始化提供器
        
        Args:
            data_dir (str): 數據存儲目錄，默認為腳本同層目錄
        """
        # 設置日誌
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(self.TAG)
        
        # 設置數據目錄 - 修改為腳本同層目錄
        if data_dir is None:
            self.data_dir = os.getcwd()  # 使用當前工作目錄（腳本同層）
        else:
            self.data_dir = data_dir
            
        # 確保數據目錄存在
        os.makedirs(self.data_dir, exist_ok=True)
        
        # JSON 文件路徑 - 直接在腳本同層目錄
        self.json_file_path = os.path.join(self.data_dir, "recword.json")
        
    def create_fallback_json(self):
        """
        創建備用 JSON 數據
        當無法從網絡獲取數據時使用
        
        Returns:
            str: JSON 格式的備用數據
        """
        try:
            fallback_data = {
                "config_id": "R-10",
                "updateIntervalMinutes": {
                    "2G": 20,
                    "3G": 20,
                    "4G": 20,
                    "WIFI": 20
                },
                "result": [
                    {
                        "track_id": "hq_yahoo",
                        "title": "Yahoo!",
                        "title_icon_url": "",
                        "headImageUrl": "",
                        "link_type": "app",
                        "data": [
                            {
                                "text": "無法訪問Yahoo新聞，請檢查網絡連接",
                                "url": self.YAHOO_NEWS_URL,
                                "h5_url": self.YAHOO_NEWS_URL,
                                "appIconUrl": "",
                                "sourceUniqueId": "content_yahoo",
                                "package": ""
                            }
                        ],
                        "selectedStatus": False,
                        "rank_type": "Yahoo"
                    },
                    {
                        "track_id": "hq_google",
                        "title": "Google",
                        "title_icon_url": "",
                        "headImageUrl": "",
                        "link_type": "app",
                        "data": [
                            {
                                "text": "無法訪問Google新聞，請檢查網絡連接",
                                "url": self.GOOGLE_NEWS_WEB_URL,
                                "h5_url": self.GOOGLE_NEWS_WEB_URL,
                                "appIconUrl": "",
                                "sourceUniqueId": "content_google",
                                "package": ""
                            }
                        ],
                        "selectedStatus": False,
                        "rank_type": "Google"
                    }
                ],
                "hash": "news_fallback",
                "qt": "composite_ad_news",
                "message": "success",
                "cost": 20,
                "status": 0
            }
            
            return json.dumps(fallback_data, ensure_ascii=False, indent=2)
            
        except Exception as e:
            self.logger.error(f"創建備用 JSON 失敗: {e}")
            return '{"status":0,"message":"success","hash":"fallback","result":[]}'
    
    def fetch_google_news_rss(self):
        """
        從 Google 新聞 RSS 獲取熱門新聞
        
        Returns:
            list: 新聞項目列表
        """
        self.logger.info("正在從Google新聞RSS獲取熱詞")
        
        try:
            # 設置請求頭
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            }
            
            # 創建請求
            req = urllib.request.Request(self.GOOGLE_NEWS_URL, headers=headers)
            
            # 發送請求
            with urllib.request.urlopen(req, timeout=20) as response:
                if response.status != 200:
                    self.logger.error(f"Google News RSS 請求失敗，響應碼：{response.status}")
                    return []
                
                # 讀取響應內容
                xml_content = response.read().decode('utf-8', errors='ignore')
            
            # 解析 RSS XML
            news_array = []
            try:
                root = ET.fromstring(xml_content)
                
                # 查找所有 item 元素
                items = root.findall('.//item')
                
                for item in items[:self.MAX_NEWS_ITEMS]:
                    title_elem = item.find('title')
                    link_elem = item.find('link')
                    
                    if title_elem is not None and link_elem is not None:
                        title = title_elem.text
                        link = link_elem.text
                        
                        if title and link:
                            # 清理標題
                            title = self.clean_title(title)
                            
                            if not self.should_exclude_text(title):
                                news_item = {
                                    "text": title,
                                    "url": link,
                                    "h5_url": link,
                                    "appIconUrl": "",
                                    "sourceUniqueId": "content_google",
                                    "package": ""
                                }
                                news_array.append(news_item)
                
                self.logger.info(f"從Google News RSS獲取到 {len(news_array)} 個新聞項目")
                return news_array
                
            except ET.ParseError as e:
                self.logger.error(f"解析Google News RSS XML失敗: {e}")
                return []
            
        except (URLError, HTTPError, Exception) as e:
            self.logger.error(f"獲取Google新聞RSS時出錯：{e}")
            return []

    def fetch_yahoo_news_trending(self):
        """
        從 Yahoo 新聞獲取熱門新聞
        
        Returns:
            list: 新聞項目列表
        """
        self.logger.info("正在從Yahoo新聞獲取熱詞")
        
        try:
            # 設置請求頭
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
            }
            
            # 創建請求
            req = urllib.request.Request(self.YAHOO_NEWS_URL, headers=headers)
            
            # 發送請求
            with urllib.request.urlopen(req, timeout=20) as response:
                if response.status != 200:
                    self.logger.error(f"Yahoo News 請求失敗，響應碼：{response.status}")
                    return []
                
                # 讀取響應內容
                html_content = response.read().decode('utf-8', errors='ignore')
            
            # 解析 HTML 內容
            news_array = []
            self.parse_yahoo_html(html_content, news_array)
            
            self.logger.info(f"從Yahoo News獲取到 {len(news_array)} 個新聞項目")
            return news_array
            
        except (URLError, HTTPError, Exception) as e:
            self.logger.error(f"獲取Yahoo新聞熱詞時出錯：{e}")
            return []
    
    def parse_yahoo_html(self, html_content, news_array):
        """
        解析 Yahoo HTML 內容，提取新聞標題和鏈接
        
        Args:
            html_content (str): HTML 內容
            news_array (list): 用於存儲新聞項目的列表
        """
        self.logger.info("開始解析Yahoo HTML內容，準備提取新聞標題")
        
        try:
            # 第一種匹配模式：針對文章鏈接
            pattern1 = re.compile(r'<a\s+[^>]*href=["\'](\\.?/articles[^"\']*)["\'][^>]*>([^<]*)</a>', re.IGNORECASE)
            matches = pattern1.finditer(html_content)
            
            for match in matches:
                if len(news_array) >= self.MAX_NEWS_ITEMS:
                    break
                
                url = match.group(1)
                title = match.group(2)
                
                # 清理標題
                title = self.clean_title(title)
                
                if self.should_exclude_text(title):
                    continue
                
                # 檢查URL是否有效
                if self.should_exclude_url(url):
                    continue
                
                if title and url:
                    news_item = {
                        "text": title,
                        "url": url,
                        "h5_url": url,
                        "appIconUrl": "",
                        "sourceUniqueId": "content_yahoo",
                        "package": ""
                    }
                    news_array.append(news_item)
            
            # 如果第一種模式沒有找到足夠的新聞，嘗試第二種模式
            if len(news_array) == 0:
                self.logger.info("嘗試使用第二種匹配模式")
                pattern2 = re.compile(r'<a\s+[^>]*class=["\']([^"\']*(?:gPFEn|IFHyqb|IBr9hb)[^"\']*)["\'][^>]*href=["\']([^"\']*)["\'][^>]*>([^<]*)</a>', re.IGNORECASE)
                matches = pattern2.finditer(html_content)
                
                for match in matches:
                    if len(news_array) >= self.MAX_NEWS_ITEMS:
                        break
                    
                    url = match.group(2)
                    title = match.group(3)
                    
                    title = self.clean_title(title)
                    
                    if self.should_exclude_text(title):
                        continue
                    
                    # 檢查URL是否有效
                    if self.should_exclude_url(url):
                        continue
                    
                    if title and url:
                        news_item = {
                            "text": title,
                            "url": url,
                            "h5_url": url,
                            "appIconUrl": "",
                            "sourceUniqueId": "content_yahoo",
                            "package": ""
                        }
                        news_array.append(news_item)
            
            # 如果仍然沒有找到足夠的新聞，嘗試第三種更寬泛的模式
            if len(news_array) == 0:
                self.logger.info("嘗試使用第三種匹配模式")
                pattern3 = re.compile(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]{10,})</a>', re.IGNORECASE)
                matches = pattern3.finditer(html_content)
                
                for match in matches:
                    if len(news_array) >= self.MAX_NEWS_ITEMS:
                        break
                    
                    url = match.group(1)
                    title = match.group(2)
                    
                    # 限制標題長度
                    if len(title) > 255:
                        title = title[:255]
                    
                    title = self.clean_title(title)
                    
                    if self.should_exclude_text(title):
                        continue
                    
                    # 處理相對鏈接
                    if not url.startswith('http'):
                        if url.startswith('./'):
                            url = self.YAHOO_NEWS_URL + url[2:]
                        elif url.startswith('/'):
                            url = self.YAHOO_NEWS_URL + url
                    
                    # 檢查URL是否有效
                    if self.should_exclude_url(url):
                        continue
                    
                    if title and url:
                        news_item = {
                            "text": title,
                            "url": url,
                            "h5_url": url,
                            "appIconUrl": "",
                            "sourceUniqueId": "content_yahoo",
                            "package": ""
                        }
                        news_array.append(news_item)
            
            self.logger.info(f"最終提取 {len(news_array)} 個新聞項目")
            
        except Exception as e:
            self.logger.error(f"解析HTML失敗: {e}")
    
    def clean_title(self, title):
        """
        清理新聞標題，去除來源信息
        
        Args:
            title (str): 原始標題
            
        Returns:
            str: 清理後的標題
        """
        if not title:
            return title
        
        # 去除HTML轉義字符
        title = unescape(title).strip()
        
        # 去除常見的新聞來源格式
        # 模式1: 標題 - 來源
        # 模式2: 標題 | 分類 - 來源
        # 模式3: 標題 - 來源名
        import re
        
        # 匹配 " - 來源" 或 " | 分類 - 來源" 格式
        patterns = [
            r'\s*\|\s*[^|]*\s*-\s*[^-]*$',  # 匹配 " | 分類 - 來源"
            r'\s*-\s*[^-]*$',               # 匹配 " - 來源"
        ]
        
        for pattern in patterns:
            title = re.sub(pattern, '', title)
        
        return title.strip()
    
    def should_exclude_text(self, text):
        """
        判斷是否應該排除某個文本
        
        Args:
            text (str): 要檢查的文本
            
        Returns:
            bool: True 表示應該排除，False 表示可以使用
        """
        if not text:
            return True
        
        # 排除的文本模式
        exclude_patterns = [
            "很抱歉，您使用的瀏覽器版本過低",
            "建議改用",
            "Yahoo Chrome, Firefox, Microsoft Edge",
            "Google Chrome, Firefox, Microsoft Edge",
            "以獲得最佳瀏覽經驗",
            "Manage history",
            "{notificationCenterNavMsg}",
            "瀏覽器版本過低",
            "最佳瀏覽經驗",
            "browser version",
            "Internet Explorer"
        ]
        
        # 檢查是否包含任何排除模式
        text_lower = text.lower()
        for pattern in exclude_patterns:
            if pattern.lower() in text_lower:
                return True
        
        # 如果文本太短（少於5個字符）也排除
        if len(text.strip()) < 5:
            return True
        
        return False
    
    def should_exclude_url(self, url):
        """
        判斷是否應該排除某個URL
        
        Args:
            url (str): 要檢查的URL
            
        Returns:
            bool: True 表示應該排除，False 表示可以使用
        """
        if not url:
            return True
        
        # 排除的URL模式
        exclude_url_patterns = [
            "javascript:",
            "mailto:",
            "#",
            "microsoft.com/zh-tw/download/internet-explorer",
            "download/internet-explorer"
        ]
        
        url_lower = url.lower()
        for pattern in exclude_url_patterns:
            if pattern in url_lower:
                return True
        
        # URL必須是有效的http或https鏈接
        if not (url.startswith('http://') or url.startswith('https://')):
            return True
        
        return False
    
    def read_local_json_file(self):
        """
        從本地文件讀取 JSON 數據
        
        Returns:
            str: JSON 字符串，如果文件不存在或讀取失敗則返回 None
        """
        try:
            if os.path.exists(self.json_file_path):
                with open(self.json_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.logger.info("成功從本地文件讀取JSON數據")
                return content
        except Exception as e:
            self.logger.error(f"讀取本地JSON文件失敗: {e}")
        
        return None
    
    def save_json_to_file(self, json_string):
        """
        將 JSON 字符串保存到本地文件
        
        Args:
            json_string (str): 要保存的 JSON 字符串
        """
        try:
            # 確保目錄存在
            os.makedirs(self.data_dir, exist_ok=True)
            
            with open(self.json_file_path, 'w', encoding='utf-8') as f:
                f.write(json_string)
            
            self.logger.info(f"成功保存JSON到文件，大小：{len(json_string)} 字節")
            
        except Exception as e:
            self.logger.error(f"保存JSON到文件失敗：{e}")
    
    def get_hot_words_json(self, request_type=None):
        """
        獲取熱詞 JSON 數據
        這是主要的公共接口方法，同時從Yahoo和Google獲取新聞
        
        Args:
            request_type (str): 請求類型（原 smali 中的參數，這裡保留接口兼容性）
            
        Returns:
            str: JSON 格式的熱詞數據
        """
        self.logger.info("開始從Yahoo和Google新聞獲取熱詞")
        
        # 清除舊的 JSON 文件
        try:
            if os.path.exists(self.json_file_path):
                os.remove(self.json_file_path)
                self.logger.info("已清除舊的 JSON 文件")
        except Exception as e:
            self.logger.warning(f"清除舊 JSON 文件時出錯: {e}")
        
        # 從網絡獲取數據
        yahoo_news = self.fetch_yahoo_news_trending()
        google_news = self.fetch_google_news_rss()
        
        # 構建完整的 JSON 響應
        result = []
        
        # 添加Yahoo新聞
        if yahoo_news:
            yahoo_section = {
                "track_id": "hq_yahoo",
                "title": "Yahoo!",
                "title_icon_url": "",
                "headImageUrl": "",
                "link_type": "app",
                "data": yahoo_news,
                "selectedStatus": False,
                "rank_type": "rank_ahoo"
            }
            result.append(yahoo_section)
        
        # 添加Google新聞
        if google_news:
            google_section = {
                "track_id": "hq_google",
                "title": "Google",
                "title_icon_url": "",
                "headImageUrl": "",
                "link_type": "app",
                "data": google_news,
                "selectedStatus": False,
                "rank_type": "rank_google"
            }
            result.append(google_section)
        
        # 如果沒有獲取到任何新聞，使用備用數據
        if not result:
            self.logger.info("使用備用數據")
            return self.create_fallback_json()
        
        response_data = {
            "config_id": "R-10",
            "updateIntervalMinutes": {
                "2G": 20,
                "3G": 20,
                "4G": 20,
                "WIFI": 20
            },
            "result": result,
            "hash": "c2d15b8822404d2ea10f48b759eadba1",
            "qt": "composite_ad_yahoo_google",
            "message": "success",
            "cost": random.randint(10, 50),
            "status": 0
        }
        
        json_result = json.dumps(response_data, ensure_ascii=False, indent=2)
        self.save_json_to_file(json_result)
        self.logger.info(f"從網絡獲取並保存熱詞數據，JSON長度：{len(json_result)}")
        
        return json_result


def main():
    """主函數，用於測試 NewsHotWordProvider"""
    # 創建提供器實例
    provider = NewsHotWordProvider()
    
    # 獲取熱詞數據
    print("正在獲取 Yahoo 和 Google 新聞熱詞...")
    hot_words_json = provider.get_hot_words_json()
    
    # 格式化輸出
    try:
        data = json.loads(hot_words_json)
        print("\n=== 獲取到的新聞熱詞 ===")
        print(f"狀態: {data.get('message', 'unknown')}")
        
        # 顯示每個來源的新聞
        for section in data.get('result', []):
            section_title = section.get('title', 'Unknown')
            news_items = section.get('data', [])
            print(f"\n--- {section_title} ({len(news_items)} 條新聞) ---")
            
            # 顯示前5條新聞標題
            for i, item in enumerate(news_items[:5]):
                print(f"{i+1}. {item.get('text', 'N/A')}")
            
            if len(news_items) > 5:
                print(f"... 還有 {len(news_items) - 5} 條新聞")
            
    except json.JSONDecodeError:
        print("JSON 解析失敗")
        print(hot_words_json)


if __name__ == "__main__":
    main()
