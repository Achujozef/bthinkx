"""
URL configuration for BThinkX project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include, reverse
from django.conf import settings
from django.conf.urls.static import static

from django.contrib.sitemaps.views import sitemap
from django.contrib.sitemaps import Sitemap

# One-page static sitemap
class StaticSitemap(Sitemap):
    changefreq = "monthly"
    priority = 1.0

    def items(self):
        return ['home']

    def location(self, item):
        return reverse(item)

sitemaps = {
    'static': StaticSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)