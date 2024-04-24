# -*- coding: utf-8 -*-
import time
from requests import Session, Response
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from typing import Optional, Dict, Union, Tuple


class APIError(Exception):
    pretext = ''

    def __init__(self, message, *args):
        if self.pretext:
            message = f"{self.pretext}: {message}"
        super().__init__(message, *args)


class APIRequests:
    def __init__(self,
                 retry_total: int = 5,
                 backoff_factor: int = 2,
                 connect_timeout: float = 30.0,
                 read_timeout: float = 60.0,
                 cert: Optional[Tuple[str, str]] = None,
                 ):
        self.retry_total = retry_total
        self.backoff_factor = backoff_factor
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout

        session = Session()
        retries = Retry(total=self.retry_total,
                        backoff_factor=self.backoff_factor,
                        status_forcelist=[500, 502, 503, 504])
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))
        session.cert = cert
        self.session: Optional[Session] = session

    def close(self):
        if self.session:
            self.session.close()
            self.session = None

    def request_get(self, url: str, headers: Dict, payload: Dict) -> Response:
        try:
            response = self.session.get(url=url,
                                        params=payload,
                                        headers=headers,
                                        timeout=(self.connect_timeout, self.read_timeout))
            time.sleep(1)
        except Exception:
            raise APIError('API exception error during requests.get')

        return response

    def request_post(self, url: str, headers: Dict, data: Union[Dict, str, bytes]) -> Response:
        try:
            response = self.session.post(url=url,
                                         headers=headers,
                                         data=data,
                                         timeout=(self.connect_timeout, self.read_timeout))
            time.sleep(1)
        except Exception:
            raise APIError('API post error during requests.post')

        return response
