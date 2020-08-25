from django import template
import re


register = template.Library()


@register.filter(name='hash')
def hash(h, key):
    return h[key]


@register.filter(name='dict')
def dict(h):
    return None


@register.filter(name='verbose_name')
def verbose_name(obj):
    return obj._meta.verbose_name


@register.filter(name='app_name')
def app_name(obj):
    return obj._meta.app_label