import aiohttp
import os
from dateutil import parser
from time import time


class AuthModel:

    def __init__(self):
        self._auth_url = None
        self._username = None
        self._password = None
        self._user_domain_name = None
        self._project_domain_name = None
        self._project_id = None
        self._project_name = None
        self._region_name = None
        self._application_credential_id = None
        self._application_credential_secret = None
        self._verify_ssl = True

    async def authenticate(self):
        raise NotImplementedError

    @property
    def os_auth_url(self):
        return self._auth_url or os.environ.get('OS_AUTH_URL')

    @property
    def os_username(self):
        return self._username or os.environ.get('OS_USERNAME')

    @property
    def os_password(self):
        return self._password or os.environ.get('OS_PASSWORD')

    @property
    def os_user_domain_name(self):
        return self._user_domain_name or os.environ.get('OS_USER_DOMAIN_NAME')

    @property
    def os_project_domain_name(self):
        return self._project_domain_name or self.os_user_domain_name

    @property
    def os_project_id(self):
        return self._project_id or os.environ.get('OS_PROJECT_ID')

    @property
    def os_project_name(self):
        return self._project_name or os.environ.get('OS_PROJECT_NAME')

    @property
    def os_region_name(self):
        return self._region_name or os.environ.get('OS_REGION_NAME')

    @property
    def os_application_credential_id(self):
        return self._application_credential_id or os.environ.get('OS_APPLICATION_CREDENTIAL_ID')

    @property
    def os_application_credential_secret(self):
        return self._application_credential_secret or os.environ.get('OS_APPLICATION_CREDENTIAL_SECRET')

    @property
    def os_verify_ssl(self):
        return self._verify_ssl or os.environ.get(bool('OS_VERIFY_SSL'), True)

class AuthPassword(AuthModel):

    def __init__(self, auth_url=None, username=None, password=None, project_name=None,
                 user_domain_name=None, project_domain_name=None,
                 application_credential_id=None, application_credential_secret=None, verify_ssl=True):
        super().__init__()
        self._auth_url = auth_url
        self._username = username
        self._password = password
        self._project_name = project_name
        self._user_domain_name = user_domain_name
        self._project_domain_name = project_domain_name
        self._application_credential_id = application_credential_id
        self._application_credential_secret = application_credential_secret
        self._verify_ssl = verify_ssl

        self._auth_endpoint = self.os_auth_url + '/auth/tokens'
        self.token = None
        self.token_expires_at = 0
        self.headers = {
            'Content-Type': 'application/json'
        }

        self._auth_payload = {'auth': {}}
        for key_from_property in (self._identity, self._scope):
            self._auth_payload['auth'].update(key_from_property)

    def is_token_valid(self):
        return self.token_expires_at - time() > 0

    @property
    def _identity(self):
        if self.os_application_credential_id and self.os_application_credential_secret:
            return {"identity": {
                "methods": ["application_credential"],
                "application_credential": {
                    "id": self.os_application_credential_id,
                    "secret": self.os_application_credential_secret
                }
            }
            }
        else:
            return {"identity": {
                'methods': ['password'],
                'password': {
                    'user': {
                        'domain': {
                            'name': self.os_user_domain_name
                        },
                        'name': self.os_username,
                        'password': self.os_password
                    }
                }
            }}

    @property
    def _scope(self):
        if self.os_application_credential_id and self.os_application_credential_secret:
            # The scope is automatically determined from the application_credential
            return {}
        else:
            return {"scope": {
                "project": {
                    "domain": {
                        "name": self.os_project_domain_name
                    },
                    "name": self.os_project_name
                }
            }}

    async def get_token(self):
        async with aiohttp.ClientSession() as session:
            async with session.post(self._auth_endpoint, json=self._auth_payload, headers=self.headers, verify_ssl=self._verify_ssl) as response:
                result = await response.json()
                return (
                    response.headers['X-Subject-Token'],
                    parser.parse(result['token']['expires_at']).timestamp(),
                    result['token']['catalog']
                )

    def get_endpoint_url(self, endpoint_name, prefered_interface="public"):
        try:
            for endpoint in self.endpoints:
                if endpoint['name'] == endpoint_name:
                    return [url['url'] for url in endpoint['endpoints'] if url['interface'] == prefered_interface][0]
        except IndexError:
            raise ValueError("could not find desired interface")
        raise ValueError("endpoint %s not found" % endpoint_name)

    async def authenticate(self):
        if self.token is None or self.is_token_valid() is False:
            self.token, self.token_expires_at, self.endpoints = await self.get_token()
