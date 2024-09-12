import json
import os
import shutil
import zipfile
import requests
from bs4 import BeautifulSoup
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import base64
import nacl.bindings
import nacl.encoding
import nacl.utils

# 禁用安全请求警告
LOCAL_PATH = ''
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
# 从环境变量中获取 secrets
try:
    with open('config.json', mode='r', encoding='utf-8') as f:
        config_json = f.read()
    configs = json.loads(config_json)
    TELEGRAM_BOT_TOKEN = configs['TELEGRAM_BOT_TOKEN']
    TELEGRAM_CHAT_ID = configs['TELEGRAM_CHAT_ID']
    VX_BOT_KEY = configs['VX_BOT_KEY']
    GITHUB_PAT = configs['GITHUB_PAT']
    DOWNLOAD_URL_MAIN = configs['DOWNLOAD_URL_MAIN']
    GITHUB_URL = configs['GITHUB_URL']
except Exception as e:
    print(f'读取 config.json 文件时出错: {e}')
    exit(1)
MOD_COOKIE = os.getenv('MOD_COOKIE')
LOCAL_VERSION = os.getenv('LOCAL_VERSION')

class ModDownloader:
    def __init__(self):
        self.local_version = LOCAL_VERSION
        self.local_path = LOCAL_PATH
        self.mod_cookies = MOD_COOKIE
        self.session = None

    def create_requests_session(self):
        """创建一个配置好的请求会话。"""
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.verify = False  # 忽略 SSL 验证
        return session

    def fetch_webpage_and_parse_html(self, url):
        #获取网页内容。
        try:
            response = self.session.get(url)
            response.raise_for_status()
            #解析 HTML 并提取版本号和文件 ID
            soup = BeautifulSoup(response.text, 'html.parser')
            title_meta = soup.find('meta', {'name': 'twitter:title'})
            original_mod_title = title_meta['content'] if title_meta else None
            mod_title = original_mod_title.replace(" ", "_")
            version_meta = soup.find('meta', {'property': 'twitter:data1'})
            version_number = version_meta['content'] if version_meta else None
            file_element = soup.find('dt', class_='file-expander-header clearfix accopen')
            file_id = file_element.get('data-id') if file_element else None
            return mod_title, version_number, file_id
        except requests.RequestException as e:
            print(f"请求过程中发生错误: {e}")
            self.send_message(f"获取mod信息出错:{e}")
            exit(1)

    def generate_download_url(self, file_id):
        """生成下载 URL。"""
        url = DOWNLOAD_URL_MAIN
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Cookie": self.mod_cookies,
            "Origin": "https://www.nexusmods.com",
            "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Microsoft Edge";v="126"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "Windows",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
            "X-Requested-With": "XMLHttpRequest",
        }
        data = {
            'fid': file_id,
            'game_id': '4333',
        }
        try:
            response = self.session.post(url, data=data, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            if isinstance(response_data, dict):
                self.send_message(f"获取下载链接成功{response_data.get('url')}")
                return response_data.get('url')
            else:
                print(f"返回的数据不是字典，而是 {type(response_data)}.")
                self.send_message(f"Cookie已失效,返回数据失败,前往https://www.nexusmods.com/eldenring/mods/510?tab=files")
                return None
        except (requests.RequestException, ValueError) as e:
            print(f"请求过程中发生错误: {e}")
            self.send_message(f"Cookie已失效,请求发生错误,前往https://www.nexusmods.com/eldenring/mods/510?tab=files")
            exit(1)

    def download_and_extract_file(self, download_url, mod_info):
        """下载文件并解压。"""
        if download_url:
            try:
                file_response = self.session.get(download_url, stream=True)
                file_response.raise_for_status()
                file_name = f"{mod_info}.zip"
                save_path = os.path.join(self.local_path, file_name)
                with open(save_path, 'wb') as file:
                    for chunk in file_response.iter_content(chunk_size=65536):
                        if chunk:
                            file.write(chunk)
                print(f"文件已成功下载至 {save_path}。")
                self.send_message("文件下载完成")

                # 解压文件
                extract_path = os.path.join(self.local_path, f"{mod_info}")
                with zipfile.ZipFile(save_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)

                # 检查解压后的文件
                files_in_zip = zip_ref.namelist()
                all_files_extracted = all(os.path.exists(os.path.join(extract_path, file_name)) and os.path.getsize(os.path.join(extract_path, file_name)) > 0 for file_name in files_in_zip)

                if all_files_extracted:
                    print(f"所有文件已成功解压至 {extract_path}。")
                    # 将文件路径和版本号写入文本文件
                    with open("file_path.txt", "w") as file:
                        file.write(save_path)
                    # 删除解压后的文件
                    shutil.rmtree(extract_path)
                    print(f"解压后的文件已被删除。")
                    self.send_message("文件已校验成功")
                    return save_path
                else:
                    print(f"部分文件未正确从 {save_path} 中解压。")
                    self.send_message(f"部分文件未正确从 {save_path} 中解压。")
            except Exception as e:
                print(f"文件处理过程中发生错误: {e}")
                self.send_message(f"文件处理过程中发生错误: {e}")
                exit(1)
            return False

    def check_version_before_download(self, mod_info):

        """从 GitHub API 获取最新的发行版版本号。"""
        url = f"{GITHUB_URL}/releases"
        headers = {'Authorization': f'token {GITHUB_PAT}'}
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                releases = response.json()
                if not releases:
                    print(f"{mod_info}项目仓库发行版未建立，开始下载。")
                    self.send_message(f"{mod_info}项目仓库发行版未建立，开始下载。")
                    return True
                # 遍历每个发行版
                for release in releases:
                    if isinstance(release, dict) and mod_info in release.get('name', ''):
                        print(f"{mod_info}当前版本已是最新，无需重新下载了。")
                        # self.send_message(f"{mod_info}当前版本已是最新，无需重新下载了。")
                        return False
                print(f"{mod_info}发行版发现新版本，开始下载。")
                self.send_message(f"{mod_info}发行版发现新版本，开始下载。")
                return True
            elif response.status_code == 401:
                print("github密钥已失效,前往https://github.com/settings/personal-access-tokens/new重新获取")
                self.send_message("github密钥已失效,前往https://github.com/settings/personal-access-tokens/new重新获取")
                return False
            elif response.status_code == 404:
                print(f"{mod_info}项目仓库不存在或没有权限访问。")
                self.send_message(f"{mod_info}项目仓库不存在或没有权限访问。")
                return False
            else:
                print(f"{mod_info}请求失败，状态码: {response.status_code}")
                self.send_message(f"{mod_info}请求失败，状态码: {response.status_code}")
                print(f"错误信息: {response.text}")
                self.send_message(f"错误信息: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"{mod_info}仓库项目已不再: {e}")
            self.send_message(f"{mod_info}仓库项目已不再: {e}")
            return False

        print(f"{mod_title}当前版本已是最新，无需重新下载。~")
        # self.send_message(f"{mod_title}当前版本已是最新，无需重新下载。~")
        return False

    def create_github_release(self, mod_info, file_path):
        """创建 GitHub 发行版并上传文件。"""
        url = f"{GITHUB_URL}/releases"
        headers = {
            'Authorization': f'token {GITHUB_PAT}',
            'Accept': 'application/vnd.github.v3+json'
        }
        release_payload = {
            "tag_name": mod_info,
            "target_commitish": "main",
            "name": mod_info,
            "body": "New version of the mod.",
            "draft": False,
            "prerelease": False
        }

        # 创建发行版
        response = requests.post(url, headers=headers, json=release_payload)
        if response.status_code == 201:
            release_info = response.json()
            release_id = release_info['id']
            upload_url = release_info['upload_url'].split('{')[0]

            # 上传文件
            file_name = os.path.basename(file_path)
            upload_url = upload_url + "?name=" + file_name
            with open(file_path, 'rb') as file:
                headers['Content-Type'] = 'application/zip'  # 设置正确的 MIME 类型
                response = requests.post(upload_url, headers=headers, data=file.read())
                if response.status_code == 201:
                    print(f"文件 {file_name} 已成功上传到发行版。")
                    self.send_message(f"文件 {file_name} 已成功上传到发行版。")
                else:
                    print(f"文件上传失败: {response.text}")
                    self.send_message(f"文件上传失败: {response.text}")
        elif response.status_code == 422:
            print(f"{url}创建发行版失败: 已有相同的版本")
            self.send_message(f"{url}文件上传失败: 已有相同的版本")
        else:
            print(f"{url}创建发行版失败: {response.text}")
            self.send_message(f"{url}文件上传失败: {response.text}")

    def send_message(self, message):
        self.send_telegram_message(message)
        self.send_VX_Bot_message(message)

    def send_telegram_message(self, message):
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message
        }
        headers = {
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                print(f"发送消息到Telegram失败: {response.text}")
        except Exception as e:
            print(f"发送消息到Telegram时出错: {e}")

    def send_VX_Bot_message(self, message):
        url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={VX_BOT_KEY}"
        payload = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }
        headers = {
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                print(f"发送消息到VX_BOT失败: {response.text}")
        except Exception as e:
            print(f"发送消息到VX_Bot时出错: {e}")
    def run(self, url_main):
        """运行下载流程。"""
        self.session = self.create_requests_session()

        # 获取网页内容并解析 HTML
        mod_title, version_number, file_id = self.fetch_webpage_and_parse_html(url_main)
        print(f"模组标题: {mod_title}")
        print(f"模组版本号: {version_number}")
        print(f"文件 ID: {file_id}")
        mod_info = f"{mod_title}_v{version_number}"

        # 检查版本
        if self.check_version_before_download(mod_info):
            # 生成下载 URL
            download_url = self.generate_download_url(file_id)
            print(f"下载链接: {download_url}")

            # 下载并解压文件
            file_path = self.download_and_extract_file(download_url, mod_info)
            if file_path:
                print("下载并解压文件成功。")
                # 创建 GitHub 发行版
                self.create_github_release(mod_info, file_path)

        # 关闭会话
        self.session.close()

if __name__ == "__main__":
    downloader = ModDownloader()
    try:
        with open('url.json', mode='r', encoding='utf-8') as f:
            url_json = f.read()
        urls = json.loads(url_json)
        for url in urls:
            url_main = url['URL_MAIN']
            downloader.run(url_main)
    except Exception as e:
        print(f'读取 url.json 文件时出错: {e}')
        exit(1)
