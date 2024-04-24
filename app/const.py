# -*- coding: utf-8 -*-

from pit import Pit
import os
import configparser

# 親ディレクトリをアプリケーションのホーム(${app_home})に設定
APP_HOME = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PACKAGE_NAME = 'app'
BASE_DIR = os.path.join(APP_HOME, PACKAGE_NAME)

# 設定情報読み込み
# conf.cfg
CFG_BASE_PATH = os.path.join(BASE_DIR, 'config')
CFG = configparser.ConfigParser()
CFG_CONF_FILE_PATH = os.path.join(CFG_BASE_PATH, 'config.cfg')
CFG.read(CFG_CONF_FILE_PATH, encoding='utf-8')

# 認証情報取得(Pit)
CREDENTIALS = {
    'yahoo_shopping': Pit.get('YahooShopping'),
    'au_pay_market': Pit.get('AuPayMarket'),
    'rms': Pit.get('RMS'),
    'yjdn': Pit.get('YJDN'),
    'mq': Pit.get('MQ'),
}


# ------- ディレクトリ定義 ----------
# ログ
LOG_DIRNAME = CFG.get('dir.common', 'log_dirname')
LOG_DIR = os.path.join(BASE_DIR, LOG_DIRNAME)
# 一時ファイル
TMP_DIRNAME = CFG.get('dir.common', 'tmp_dirname')
TMP_DIR = os.path.join(BASE_DIR, TMP_DIRNAME)
# Chromeプロファイル
CHROME_PROFILE_DIRNAME = CFG.get('dir.common', 'profile_dirname')
CHROME_PROFILE_DIR = os.path.join(BASE_DIR, CHROME_PROFILE_DIRNAME)
# wsdl
WSDL_DIRNAME = CFG.get('dir.common', 'wsdl_dirname')
WSDL_DIR = os.path.join(BASE_DIR, WSDL_DIRNAME)
# 証明書
CERT_DIRNAME = CFG.get('dir.common', 'cert_dirname')
CERT_DIR = os.path.join(BASE_DIR, CERT_DIRNAME)

# ------- 本番環境/ローカル開発環境切り替え ----------
IS_PRODUCTION = CFG.getboolean('env.common', 'is_production')


# ------- ログ設定 ----------
LOG_SETTING_LOG_LEVEL = CFG.get('logger_setting.common', 'log_level')
LOG_SETTING_MAX_FILE_SIZE = CFG.getint('logger_setting.common', 'log_max_file_size')
LOG_SETTING_BACKUP_FILE_COUNT = CFG.getint('logger_setting.common', 'log_backup_file_count')
LOG_SETTING_STDOUT = CFG.getboolean('logger_setting.common', 'log_stdout')
LOG_SETTING_RAISE_EXCEPTION = CFG.getboolean('logger_setting.common', 'log_raise_exception')
LOG_SETTING_FORMAT = "%(asctime)s | %(levelname)s | %(process)d | %(thread)d | %(module)s | %(funcName)s | %(lineno)d | %(message)s"
LOG_SETTING = {
    'log_dir': LOG_DIR,
    'raise_exceptions': LOG_SETTING_RAISE_EXCEPTION,
    'log_level': LOG_SETTING_LOG_LEVEL,
    'stdout': LOG_SETTING_STDOUT,
    'max_file_size': LOG_SETTING_MAX_FILE_SIZE,
    'backup_file_count': LOG_SETTING_BACKUP_FILE_COUNT,
    'log_format': LOG_SETTING_FORMAT,
}


# ------- YJDN(Yahoo! JAPAN Developer Network) ----------
# 認証情報
if IS_PRODUCTION:
    YJDN_APP_ID_PRODUCER = CREDENTIALS['yjdn']['production']['stockout'][1]['application_id']
    YJDN_SECRET_PRODUCER = CREDENTIALS['yjdn']['production']['stockout'][1]['secret']
    YJDN_APP_ID_CONSUMER = CREDENTIALS['yjdn']['production']['stockout'][2]['application_id']
    YJDN_SECRET_CONSUMER = CREDENTIALS['yjdn']['production']['stockout'][2]['secret']
else:
    YJDN_APP_ID_PRODUCER = CREDENTIALS['yjdn']['test']['stockout'][1]['application_id']
    YJDN_SECRET_PRODUCER = CREDENTIALS['yjdn']['test']['stockout'][1]['secret']
    YJDN_APP_ID_CONSUMER = CREDENTIALS['yjdn']['test']['stockout'][2]['application_id']
    YJDN_SECRET_CONSUMER = CREDENTIALS['yjdn']['test']['stockout'][2]['secret']

YJDN_CALLBACK_URL = CFG.get('yjdn.common', 'callback_url')  # コールバックURL


# ------- Yahoo!ショッピング関連 ----------
# 認証情報
if IS_PRODUCTION:
    YSHOP_BUSINESS_ID = CREDENTIALS['yahoo_shopping']['production']['business_id']
    YSHOP_BUSINESS_PASSWORD = CREDENTIALS['yahoo_shopping']['production']['business_password']
    YSHOP_YAHOO_ID = CREDENTIALS['yahoo_shopping']['production']['yahoo_id']
    YSHOP_YAHOO_PASSWORD = CREDENTIALS['yahoo_shopping']['production']['yahoo_password']
else:
    YSHOP_BUSINESS_ID = CREDENTIALS['yahoo_shopping']['test']['business_id']
    YSHOP_BUSINESS_PASSWORD = CREDENTIALS['yahoo_shopping']['test']['business_password']
    YSHOP_YAHOO_ID = CREDENTIALS['yahoo_shopping']['test']['yahoo_id']
    YSHOP_YAHOO_PASSWORD = CREDENTIALS['yahoo_shopping']['test']['yahoo_password']

YSHOP_SELLER_ID = CFG.get('yshop.production', 'seller_id') if IS_PRODUCTION else CFG.get('yshop.test', 'seller_id')

# 証明書
# 秘密鍵(.key)
YSHOP_CERT_PKEY_FILENAME = CFG.get('yshop.production' if IS_PRODUCTION else 'yshop.test', 'api_cert_pkey_filename')
YSHOP_CERT_PKEY_FILE = os.path.join(CERT_DIR, YSHOP_CERT_PKEY_FILENAME) if YSHOP_CERT_PKEY_FILENAME else None
# サーバ証明書(.crt)
YSHOP_CERT_CRT_FILENAME = CFG.get('yshop.production' if IS_PRODUCTION else 'yshop.test', 'api_cert_crt_filename')
YSHOP_CERT_CRT_FILE = os.path.join(CERT_DIR, YSHOP_CERT_CRT_FILENAME) if YSHOP_CERT_CRT_FILENAME else None

# ------- 楽天関連 ----------
# 認証情報
if IS_PRODUCTION:
    RMS_API_SERVICE_SECRET = CREDENTIALS['rms']['production']['api']['service_secret']
    RMS_API_LICENSE_KEY = CREDENTIALS['rms']['production']['api']['license_key']
else:
    RMS_API_SERVICE_SECRET = CREDENTIALS['rms']['test']['api']['service_secret']
    RMS_API_LICENSE_KEY = CREDENTIALS['rms']['test']['api']['license_key']

# WSDLファイル
RMS_WSDL_FILENAME = CFG.get('rakuten.common', 'wsdl_filename')
RMS_WSDL_FILE = os.path.join(WSDL_DIR, RMS_WSDL_FILENAME)

# ------- AuPayマーケット関連 ----------
# 認証情報
if IS_PRODUCTION:
    AUPAYM_API_KEY = CREDENTIALS['au_pay_market']['production']['api']['api_key']
else:
    AUPAYM_API_KEY = CREDENTIALS['au_pay_market']['test']['api']['api_key']


AU_SHOP_ID = CFG.getint('au.common', 'shop_id')  # ショップID


# ------- ブラウザー設定 ----------
DRIVER_HEADLESS = CFG.getboolean('browser.common', 'headless')


# ------- メッセージキュー(MQ)関連 ----------
# 認証情報
MQ_USER_ID = CREDENTIALS['mq']['production']['user'] if IS_PRODUCTION else CREDENTIALS['mq']['test']['user']
MQ_PASSWORD = CREDENTIALS['mq']['production']['password'] if IS_PRODUCTION else CREDENTIALS['mq']['test']['password']

# 接続情報
MQ_HOST = CFG.get('mq.common', 'host')
MQ_EXCHANGE = CFG.get('mq.common', 'exchange')
MQ_VHOST = CFG.get('mq.production' if IS_PRODUCTION else 'mq.test', 'mq_vhost')
MQ_CONNECT = {
    'host': MQ_HOST,
    'vhost': MQ_VHOST,
    'username': MQ_USER_ID,
    'password': MQ_PASSWORD,
    'exchange': MQ_EXCHANGE,
}

# キュー
MQ_YSHOP_QUEUE = CFG.get('mq.production' if IS_PRODUCTION else 'mq.test', 'mq_yshop_queue_name')
MQ_RAKUTEN_QUEUE = CFG.get('mq.production' if IS_PRODUCTION else 'mq.test', 'mq_rakuten_queue_name')
MQ_AU_QUEUE = CFG.get('mq.production' if IS_PRODUCTION else 'mq.test', 'mq_au_queue_name')

# ルーティングキー
MQ_YSHOP_ROUTING_KEY = CFG.get('mq.production' if IS_PRODUCTION else 'mq.test', 'mq_yshop_routing_key')
MQ_RAKUTEN_ROUTING_KEY = CFG.get('mq.production' if IS_PRODUCTION else 'mq.test', 'mq_rakuten_routing_key')
MQ_AU_ROUTING_KEY = CFG.get('mq.production' if IS_PRODUCTION else 'mq.test', 'mq_au_routing_key')

# 設定情報
MQ_EXCHANGE_TYPE = CFG.get('mq.common', 'exchange_type')
MQ_PASSIVE = CFG.getboolean('mq.common', 'passive')
MQ_DURABLE = CFG.getboolean('mq.common', 'durable')
MQ_CONNECTION_ATTEMPTS = CFG.getint('mq.common', 'connection_attempts')
MQ_EXCHANGE_AUTO_DELETE = CFG.getboolean('mq.common', 'exchange_auto_delete')
MQ_QUEUE_EXCLUSIVE = CFG.getboolean('mq.common', 'queue_exclusive')
MQ_QUEUE_AUTO_DELETE = CFG.getboolean('mq.common', 'queue_auto_delete')
MQ_QOS_PRE_FETCH_COUNT = CFG.getint('mq.common', 'qos_pre_fetch_count')  # 1メッセージずつ取得
MQ_DELIVERY_MODE = CFG.getint('mq.common', 'delivery_mode')  # 再起動してもメッセージが失われないようにする

# ------- その他 ----------
ORDER_LIST_GET_LAST_DAYS = CFG.getint('etc.common', 'order_list_get_last_days')  # x日前から現在までの注文リストを取得
