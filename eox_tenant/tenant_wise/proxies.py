"""
Tenant wise proxies that allows to override the platform models.
"""
import json
import logging
from itertools import chain

import six
from django.conf import settings
from django.core.cache import cache

from eox_tenant.edxapp_wrapper.dark_lang_middleware import get_dark_lang_middleware
from eox_tenant.edxapp_wrapper.site_configuration_module import get_site_configuration_models
from eox_tenant.models import Microsite, TenantConfig, TenantOrganization
from eox_tenant.utils import clean_serializable_values

SiteConfigurationModels = get_site_configuration_models()
DarkLangMiddleware = get_dark_lang_middleware()

TENANT_ALL_ORGS_CACHE_KEY = "tenant.all_orgs_list"
EOX_TENANT_CACHE_KEY_TIMEOUT = getattr(
    settings,
    "EOX_TENANT_CACHE_KEY_TIMEOUT",
    300
)
TENANT_MICROSITES_ITERATOR_KEY = "tenant-microsites-iterator"
logger = logging.getLogger(__name__)


class TenantSiteConfigProxy(SiteConfigurationModels.SiteConfiguration):
    """
    This a is Proxy model for SiteConfiguration from <openedx.core.djangoapps.site_configuration.models>.
    This allows to add or override methods using as base the SiteConfiguration model.
    More information in https://docs.djangoproject.com/en/3.0/topics/db/models/#proxy-models
    """

    cached_site_values = None

    class Meta:
        """ Set as a proxy model. """
        proxy = True

    def __str__(self):
        key = getattr(settings, "EDNX_TENANT_KEY", "No tenant is active at the moment")
        return "<Tenant proxy as site_configuration: {}>".format(key)

    @property
    def enabled(self):
        """
        Return True if EDNX_TENANT_KEY is in the current settings.
        """
        if getattr(settings, 'EDNX_TENANT_KEY', None):
            return True
        return False

    @enabled.setter
    def enabled(self, value):
        """
        We ignore the setter since this is a read proxy.
        """

    def get_value(self, name, default=None):
        """
        Return Configuration value from the Tenant loaded in the settings object
        as if this was a SiteConfiguration class.
        """
        try:
            return getattr(settings, name, default)
        except AttributeError as error:
            logger.exception("Invalid data at the TenantConfigProxy get_value. \n [%s]", error)

        return default

    @property
    def values(self):
        """
        Returns a serializable subset of the loaded settings.
        """
        if self.enabled:
            return vars(settings._wrapped)  # pylint: disable=protected-access
        return {}

    @values.setter
    def values(self, value):
        """
        We ignore the setter since this is a read proxy.
        """

    @property
    def site_values(self):
        """
        Returns a serializable subset of the loaded settings. This version works with juniper releases.
        """
        if self.cached_site_values:
            return self.cached_site_values
        self.cached_site_values = clean_serializable_values(self.values)
        return self.cached_site_values

    @site_values.setter
    def site_values(self, value):
        """
        We ignore the setter since this is a read proxy. This version works with juniper releases.
        """

    def save(self, *args, **kwargs):
        """
        Don't allow to save TenantSiteConfigProxy model in database.
        """

    @classmethod
    def get_all_orgs(cls):
        """
        This returns a set of orgs that are considered within all microsites and TenantConfig.
        This can be used, for example, to do filtering
        """
        # Check the cache first
        org_filter_set = cache.get(TENANT_ALL_ORGS_CACHE_KEY)

        if org_filter_set:
            return org_filter_set

        org_filter_set = set(TenantOrganization.objects.all().values_list("name", flat=True))
        cls.set_key_to_cache(TENANT_ALL_ORGS_CACHE_KEY, org_filter_set)

        return org_filter_set

    @classmethod
    def get_value_for_org(cls, org, val_name, default=None):
        """
        Returns a configuration value for a microsite or TenantConfig which has an org_filter that matches
        what is passed in.
        """
        return cls.__get_value_for_org(org, val_name, default)

    @classmethod
    def set_key_to_cache(cls, key, value):
        """
        Stores a key value pair in a cache scoped to the thread
        """
        cache.set(
            key,
            value,
            EOX_TENANT_CACHE_KEY_TIMEOUT
        )

    @classmethod
    def __get_value_for_org(cls, org, val_name, default=None):
        """
        Optimized method, that returns a value for the given org and val_name, from the
        TenantConfig or Microsite model.
        """
        cache_key = "org-value-{}-{}".format(org, val_name)

        # Make use of tenant-external-key to generate unique cache_key per
        # tenant. This will help to fetch the current tenant value if the org
        # is configured in multiple tenants/microsites including the current
        # one.
        tenat_key = getattr(settings, "EDNX_TENANT_KEY", None)
        if tenat_key is not None:
            cache_key = "{}-{}".format(cache_key, tenat_key)
        cached_value = cache.get(cache_key)

        if cached_value:
            return cached_value

        result = TenantConfig.get_value_for_org(org, val_name, tenat_key)

        if result:
            cls.set_key_to_cache(cache_key, result)
            return result

        result = Microsite.get_value_for_org(org, val_name, tenat_key)
        result = result if result else default
        cls.set_key_to_cache(cache_key, result)

        return result

    @classmethod
    def pre_load_values_by_org(cls, val_name):
        """
        Save in cache the values for all the organizations in TenantConfig and Microsite models.
        """
        pre_load_value_key = "eox-tenant-pre-load-{}-key".format(val_name)

        if cache.get(pre_load_value_key):
            return

        tenant_config = TenantConfig.objects.values_list("lms_configs", flat=True)
        microsite_config = Microsite.objects.values_list("values", flat=True)

        for config in chain(microsite_config, tenant_config):
            try:
                if isinstance(config, six.string_types):
                    config = json.loads(config)

                org_filter = config.get("course_org_filter", [])
                result = config.get(val_name)
            except AttributeError:
                continue

            if isinstance(org_filter, six.string_types):
                org_filter = [org_filter]

            for org in org_filter:
                key = "org-value-{}-{}".format(org, val_name)
                cls.set_key_to_cache(key, result)

        cls.set_key_to_cache(pre_load_value_key, True)


class DarkLangMiddlewareProxy(DarkLangMiddleware):
    """This Middleware will be used if you have FEATURES["EDNX_SITE_AWARE_LOCALE"] in True.
    This take the released_languages from the site aware settings, and set a HTTP_ACCEPT_LANGUAGE if
    you don't have one."""

    class Meta:
        """ Set as a proxy model. """
        proxy = True

    @property
    def released_langs(self):
        """
        Current list of released languages from settings.
        """

        get_language_options = getattr(settings, "released_languages", "")
        language_options = [lang.lower().strip() for lang in get_language_options.split(',')]
        if settings.LANGUAGE_CODE not in language_options:
            language_options.append(settings.LANGUAGE_CODE)
        return language_options

    def process_request(self, request):
        """
        This will be run when you do a request, and prevent user from requesting un-released languages.
        """

        # If the request doesn't have HTTP_ACCEPT_LANGUAGE, eduNEXT set it to
        # settings.LANGUAGE_CODE that is site aware so that
        # django.utils.locale.LocaleMiddleware can pick it up
        accept = request.META.get('HTTP_ACCEPT_LANGUAGE', None)
        if not accept:
            request.META['HTTP_ACCEPT_LANGUAGE'] = f"{settings.LANGUAGE_CODE};q=0.1"

        self._clean_accept_headers(request)
