import webview
import teslapy


def show_webview(url):
    """ Shows the SSO page in a webview and returns the redirected URL """
    result = ['']
    window = webview.create_window('Login', url)
    def on_loaded():
        result[0] = window.get_current_url()
        if 'void/callback' in result[0].split('?')[0]:
            window.destroy()
    try:
        window.events.loaded += on_loaded
    except AttributeError:
        window.loaded += on_loaded
    webview.start()  # Blocks the main thread until webview is closed
    return result[0]


with teslapy.Tesla('tesla@dsoworld.co.uk', authenticator=show_webview) as tesla:
    tesla.fetch_token()









