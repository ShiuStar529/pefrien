"""Integration boundary. Do not enable public hosting with development auth.

Implement provider-specific server-side code exchange, signature validation,
state/nonce checks, and (provider, subject) account mapping before enabling OAuth.
Never use a client-supplied openid or phone as verified identity.
"""
AUTH_PROVIDERS={
    'wechat':{'name':'微信','required':['app_id','app_secret','registered_callback']},
    'qq':{'name':'QQ','required':['app_id','app_key','registered_callback']},
    'alipay':{'name':'支付宝','required':['app_id','private_key','alipay_public_key','registered_callback']},
}
def send_sms(phone,code):
    raise RuntimeError('SMS adapter is not configured. Implement provider delivery before production.')
