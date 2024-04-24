# -*- coding: utf-8 -*-
import logging
import logging.handlers
import os
import json
from datetime import date, datetime


def get_logger(log_dir,
               task_name=None,
               sub_name=None,
               name_datetime: datetime = datetime.now(),
               task_no=None,
               worker_no=None,
               raise_exceptions=True,
               log_level='DEBUG',
               stdout=False,
               log_format="%(asctime)s | %(levelname)s | %(process)d | %(thread)d | %(module)s | %(funcName)s | %(lineno)d | %(message)s",
               max_file_size=1024,
               backup_file_count=10):
    names = ['log']
    if task_name:
        names.append(task_name)
    names.append(name_datetime.strftime('%Y-%m-%d'))
    if sub_name:
        names.append(sub_name)
    if task_no:
        names.append(f'task-{task_no}')
    if worker_no:
        names.append(f'worker-{worker_no}')
    log_name = '_'.join(names)

    # ロガーで例外の送出をするかどうか
    logging.raiseExceptions = raise_exceptions

    # ロガー初期化
    logger = logging.getLogger(log_name)
    logger.setLevel(log_level)

    # レコード形式
    formatter = logging.Formatter(log_format)

    # stdout
    if stdout:
        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    #  ログ保存ディレクトリ確認
    os.makedirs(log_dir, exist_ok=True)

    # logファイル名生成
    log_file_name_a = f'{log_name}.log'
    log_file = os.path.join(log_dir, log_file_name_a)
    handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=max_file_size,
        encoding='utf-8',
        backupCount=backup_file_count,
        delay=True)
    handler.setLevel(log_level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def var_dump(data):
    def json_serial(obj):
        # 日付型の場合には、文字列に変換します
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        # 上記以外はサポート対象外.
        raise TypeError("Type %s not serializable" % type(obj))

    return json.dumps(data, ensure_ascii=False, default=json_serial)
