from django.conf import settings
from django.http import HttpRequest


class NgrokHostMiddleware:
    """
    Permite domínios do ngrok em desenvolvimento.
    Adiciona automaticamente domínios *.ngrok-free.app e *.ngrok.io ao ALLOWED_HOSTS
    quando DEBUG=True, antes da validação de host do SecurityMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        # Se estiver em desenvolvimento, permite domínios ngrok
        if settings.DEBUG:
            # Acessa o host diretamente do header HTTP sem validação
            # request.get_host() já valida e lança exceção, então usamos META diretamente
            host_header = request.META.get('HTTP_HOST', '')
            if host_header:
                host = host_header.split(':')[0]  # Remove porta se houver
                
                # Verifica se é um domínio ngrok
                if host.endswith('.ngrok-free.app') or host.endswith('.ngrok.io'):
                    # Adiciona ao ALLOWED_HOSTS se não estiver lá
                    # Isso deve ser feito antes do SecurityMiddleware validar o host
                    if host not in settings.ALLOWED_HOSTS:
                        settings.ALLOWED_HOSTS.append(host)
        
        return self.get_response(request)

