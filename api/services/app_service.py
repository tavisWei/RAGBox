"""App service for managing Dify-style applications."""

from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import uuid4, UUID

from api.models.app import App, AppMode, AppSiteConfig


class AppService:
    """Service for managing applications with in-memory storage."""

    def __init__(self):
        """Initialize AppService with in-memory storage."""
        self._apps: Dict[str, App] = {}
        self._site_configs: Dict[str, AppSiteConfig] = {}

    def create_app(
        self,
        tenant_id: str,
        name: str,
        mode: str = "chat",
        description: Optional[str] = None,
        icon: Optional[str] = None,
        icon_background: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
        enable_site: bool = False,
        enable_api: bool = True,
        site_config: Optional[Dict[str, Any]] = None,
        api_config: Optional[Dict[str, Any]] = None,
    ) -> App:
        """
        Create a new application.

        Args:
            tenant_id: Tenant ID
            name: Application name
            mode: Application mode (chat, completion, agent, workflow)
            description: Optional description
            icon: Optional icon
            icon_background: Optional icon background color
            model_config: Model configuration
            enable_site: Enable public site
            enable_api: Enable API access
            site_config: Site configuration
            api_config: API configuration

        Returns:
            Created App instance
        """
        app_id = str(uuid4())
        valid_modes = [m.value for m in AppMode]
        if mode not in valid_modes:
            mode = AppMode.CHAT.value

        try:
            tenant_uuid = UUID(tenant_id)
        except (ValueError, AttributeError):
            tenant_uuid = uuid4()

        app = App(
            id=UUID(app_id),
            tenant_id=tenant_uuid,
            name=name,
            description=description,
            icon=icon,
            icon_background=icon_background,
            mode=mode,
            model_config=model_config or {},
            enable_site=enable_site,
            enable_api=enable_api,
            site_config=site_config or {},
            api_config=api_config or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self._apps[app_id] = app
        return app

    def get_app(self, app_id: str) -> Optional[App]:
        """
        Get an application by ID.

        Args:
            app_id: Application ID

        Returns:
            App instance or None if not found
        """
        return self._apps.get(app_id)

    def list_apps(
        self,
        tenant_id: str,
        mode: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[App]:
        """
        List applications for a tenant.

        Args:
            tenant_id: Tenant ID
            mode: Optional mode filter
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of App instances
        """
        apps = [app for app in self._apps.values() if str(app.tenant_id) == tenant_id]
        if mode:
            apps = [app for app in apps if app.mode == mode]
        apps.sort(key=lambda x: x.created_at, reverse=True)
        return apps[offset : offset + limit]

    def update_app(
        self,
        app_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        icon: Optional[str] = None,
        icon_background: Optional[str] = None,
        mode: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
        enable_site: Optional[bool] = None,
        enable_api: Optional[bool] = None,
        site_config: Optional[Dict[str, Any]] = None,
        api_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[App]:
        """
        Update an application.

        Args:
            app_id: Application ID
            name: New name
            description: New description
            icon: New icon
            icon_background: New icon background
            mode: New mode
            model_config: New model configuration
            enable_site: Enable/disable site
            enable_api: Enable/disable API
            site_config: New site configuration
            api_config: New API configuration

        Returns:
            Updated App instance or None if not found
        """
        app = self._apps.get(app_id)
        if not app:
            return None

        if name is not None:
            app.name = name
        if description is not None:
            app.description = description
        if icon is not None:
            app.icon = icon
        if icon_background is not None:
            app.icon_background = icon_background
        if mode is not None:
            valid_modes = [m.value for m in AppMode]
            if mode in valid_modes:
                app.mode = mode
        if model_config is not None:
            app.model_config = model_config
        if enable_site is not None:
            app.enable_site = enable_site
        if enable_api is not None:
            app.enable_api = enable_api
        if site_config is not None:
            app.site_config = site_config
        if api_config is not None:
            app.api_config = api_config

        app.updated_at = datetime.utcnow()
        return app

    def delete_app(self, app_id: str) -> bool:
        """
        Delete an application.

        Args:
            app_id: Application ID

        Returns:
            True if deleted, False if not found
        """
        if app_id in self._apps:
            del self._apps[app_id]
            if app_id in self._site_configs:
                del self._site_configs[app_id]
            return True
        return False

    def create_site_config(
        self,
        app_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        copyright: Optional[str] = None,
        privacy_policy: Optional[str] = None,
        custom_domain: Optional[str] = None,
        theme: Optional[Dict[str, Any]] = None,
    ) -> Optional[AppSiteConfig]:
        """
        Create site configuration for an app.

        Args:
            app_id: Application ID
            title: Site title
            description: Site description
            copyright: Copyright text
            privacy_policy: Privacy policy URL
            custom_domain: Custom domain
            theme: Theme configuration

        Returns:
            Created AppSiteConfig or None if app not found
        """
        if app_id not in self._apps:
            return None

        config_id = str(uuid4())
        site_config = AppSiteConfig(
            id=UUID(config_id),
            app_id=UUID(app_id),
            title=title,
            description=description,
            copyright=copyright,
            privacy_policy=privacy_policy,
            custom_domain=custom_domain,
            theme=theme or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self._site_configs[app_id] = site_config
        return site_config

    def get_site_config(self, app_id: str) -> Optional[AppSiteConfig]:
        """
        Get site configuration for an app.

        Args:
            app_id: Application ID

        Returns:
            AppSiteConfig or None if not found
        """
        return self._site_configs.get(app_id)


_app_service: Optional[AppService] = None


def get_app_service() -> AppService:
    global _app_service
    if _app_service is None:
        _app_service = AppService()
    return _app_service
