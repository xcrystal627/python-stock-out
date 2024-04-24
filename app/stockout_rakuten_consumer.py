# -*- coding: utf-8 -*-

import argparse
from datetime import datetime
from typing import Dict
import functools

import const
from logging import Logger
import logger
from mq import MQ, MQMsgData
import rapi


def _stockout(msg_data: MQMsgData, log: Logger):
    item_ids = msg_data.item_ids
    with rapi.RakutenAPI(log=log) as api:
        try:
            log.info('Request to get inventory')
            inventories = api.inventory.get(item_urls=item_ids)
        except Exception:
            raise Exception('stockout error')

        set_list = []
        for inventory_data in inventories:
            log.info('Inventory item data=%s', inventory_data)
            if inventory_data.inventory_count > 0:
                log.info('Out of stock item id=%s', inventory_data.item_url)
                set_data = rapi.InventoryUpdateData(item_url=inventory_data.item_url,
                                                    inventory_count=0)
                set_list.append(set_data)

        if set_list:
            try:
                log.info('Request to stock out list=%s', set_list)
                result = api.inventory.update(update_items=set_list)
            except Exception:
                log.exception('Failed to update stock')
                raise Exception('stockout error')
            log.info('Updated stock items=%s', set_list)
            log.info('Not updated stock items=%s', result)
            return

        log.info('N/A update stock data')


def _relist_on_message(msg: Dict, log: Logger) -> bool:
    log.info('Message data=%s', logger.var_dump(msg))
    try:
        msg_data = MQMsgData(**msg)
    except Exception:
        raise Exception('Receive message parse error')
    log.info('Get queue message data=%s', msg_data)

    _stockout(msg_data=msg_data, log=log)
    return True


def _consumer(log: Logger):
    try:
        with MQ(**const.MQ_CONNECT,
                queue=const.MQ_RAKUTEN_QUEUE,
                routing_key=const.MQ_RAKUTEN_ROUTING_KEY) as queue:
            queue.open()
            callback = functools.partial(_relist_on_message, log=log)
            queue.receive_message(callback)

    except Exception:
        log.exception('Failed to MQ connect')
        raise


def main():
    parser = argparse.ArgumentParser(description='stockout_rakuten_consumer')
    parser.add_argument('--task_no',
                        required=True,
                        type=int,
                        help='input process No type integer')

    arg_parser = parser.parse_args()
    log = logger.get_logger(task_name='stockout-rakuten-consumer',
                            sub_name='main',
                            name_datetime=datetime.now(),
                            task_no=arg_parser.task_no,
                            **const.LOG_SETTING)
    log.info('Start task')
    log.info('Input args task_no=%s', arg_parser.task_no)

    _consumer(log=log)
    log.info('End task')


if __name__ == '__main__':
    main()
