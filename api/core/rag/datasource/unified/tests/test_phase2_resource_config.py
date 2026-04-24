import pytest

from api.services.resource_config_service import (
    DatasetResourceBinding,
    ResourceConfig,
    ResourceConfigService,
    ResourceLevel,
)


class TestResourceLevel:
    def test_enum_values(self):
        assert ResourceLevel.LOW == "low"
        assert ResourceLevel.MEDIUM == "medium"
        assert ResourceLevel.HIGH == "high"


class TestResourceConfig:
    def test_creation(self):
        config = ResourceConfig(
            tenant_id="tenant_1",
            level=ResourceLevel.MEDIUM,
            data_store_type="pgvector",
            config_json={"chunk_size": 500},
        )
        assert config.tenant_id == "tenant_1"
        assert config.level == ResourceLevel.MEDIUM
        assert config.data_store_type == "pgvector"
        assert config.is_default is False


class TestResourceConfigService:
    def setup_method(self):
        ResourceConfigService.reset()

    def test_get_default_config_low(self):
        config = ResourceConfigService.get_default_config(ResourceLevel.LOW)
        assert config["data_store_type"] == "sqlite"
        assert config["vector_enabled"] is False
        assert config["max_documents"] == 10000

    def test_get_default_config_medium(self):
        config = ResourceConfigService.get_default_config(ResourceLevel.MEDIUM)
        assert config["data_store_type"] == "pgvector"
        assert config["vector_enabled"] is True
        assert config["rerank_enabled"] is True
        assert config["max_documents"] == 1000000

    def test_get_default_config_high(self):
        config = ResourceConfigService.get_default_config(ResourceLevel.HIGH)
        assert config["data_store_type"] == "elasticsearch"
        assert config["embedding_model"] == "text-embedding-3-large"
        assert config["chunk_size"] == 1000

    def test_create_config(self):
        config = ResourceConfigService.create_config(
            tenant_id="tenant_1",
            level=ResourceLevel.MEDIUM,
            config_id="cfg_1",
        )
        assert config.tenant_id == "tenant_1"
        assert config.level == ResourceLevel.MEDIUM
        assert config.data_store_type == "pgvector"
        assert config.id == "cfg_1"

    def test_create_config_with_custom(self):
        config = ResourceConfigService.create_config(
            tenant_id="tenant_1",
            level=ResourceLevel.LOW,
            custom_config={"chunk_size": 1000, "vector_enabled": True},
            config_id="cfg_2",
        )
        assert config.config_json["chunk_size"] == 1000
        assert config.config_json["vector_enabled"] is True
        assert config.config_json["data_store_type"] == "sqlite"

    def test_get_config(self):
        ResourceConfigService.create_config(
            tenant_id="tenant_1", level=ResourceLevel.MEDIUM, config_id="cfg_1"
        )
        fetched = ResourceConfigService.get_config("cfg_1")
        assert fetched is not None
        assert fetched.id == "cfg_1"

    def test_get_config_not_found(self):
        assert ResourceConfigService.get_config("nonexistent") is None

    def test_set_default_config(self):
        ResourceConfigService.create_config(
            tenant_id="tenant_1", level=ResourceLevel.MEDIUM, config_id="cfg_1"
        )
        ResourceConfigService.set_default_config("cfg_1")
        config = ResourceConfigService.get_config_for_dataset("ds_1")
        assert config is not None
        assert config.id == "cfg_1"

    def test_set_default_config_not_found(self):
        with pytest.raises(ValueError):
            ResourceConfigService.set_default_config("nonexistent")

    def test_bind_dataset_to_config(self):
        ResourceConfigService.create_config(
            tenant_id="tenant_1", level=ResourceLevel.HIGH, config_id="cfg_1"
        )
        binding = ResourceConfigService.bind_dataset_to_config("ds_1", "cfg_1")
        assert binding.dataset_id == "ds_1"
        assert binding.resource_config_id == "cfg_1"
        assert binding.resource_config is not None

    def test_bind_dataset_config_not_found(self):
        with pytest.raises(ValueError):
            ResourceConfigService.bind_dataset_to_config("ds_1", "nonexistent")

    def test_get_config_for_dataset_with_binding(self):
        ResourceConfigService.create_config(
            tenant_id="tenant_1", level=ResourceLevel.HIGH, config_id="cfg_1"
        )
        ResourceConfigService.bind_dataset_to_config("ds_1", "cfg_1")
        config = ResourceConfigService.get_config_for_dataset("ds_1")
        assert config is not None
        assert config.level == ResourceLevel.HIGH

    def test_get_config_for_dataset_fallback_default(self):
        ResourceConfigService.create_config(
            tenant_id="tenant_1", level=ResourceLevel.MEDIUM, config_id="cfg_1"
        )
        ResourceConfigService.set_default_config("cfg_1")
        config = ResourceConfigService.get_config_for_dataset("unbound_ds")
        assert config is not None
        assert config.id == "cfg_1"

    def test_get_config_for_dataset_no_fallback(self):
        assert ResourceConfigService.get_config_for_dataset("ds_1") is None

    def test_unbind_dataset(self):
        ResourceConfigService.create_config(
            tenant_id="tenant_1", level=ResourceLevel.MEDIUM, config_id="cfg_1"
        )
        ResourceConfigService.bind_dataset_to_config("ds_1", "cfg_1")
        ResourceConfigService.unbind_dataset("ds_1")
        assert ResourceConfigService.get_config_for_dataset("ds_1") is None

    def test_list_configs(self):
        ResourceConfigService.create_config(
            tenant_id="tenant_1", level=ResourceLevel.LOW, config_id="cfg_1"
        )
        ResourceConfigService.create_config(
            tenant_id="tenant_2", level=ResourceLevel.HIGH, config_id="cfg_2"
        )

        all_configs = ResourceConfigService.list_configs()
        assert len(all_configs) == 2

        tenant_configs = ResourceConfigService.list_configs(tenant_id="tenant_1")
        assert len(tenant_configs) == 1
        assert tenant_configs[0].tenant_id == "tenant_1"

    def test_delete_config(self):
        ResourceConfigService.create_config(
            tenant_id="tenant_1", level=ResourceLevel.MEDIUM, config_id="cfg_1"
        )
        ResourceConfigService.set_default_config("cfg_1")
        ResourceConfigService.bind_dataset_to_config("ds_1", "cfg_1")

        ResourceConfigService.delete_config("cfg_1")

        assert ResourceConfigService.get_config("cfg_1") is None
        assert ResourceConfigService.get_config_for_dataset("ds_1") is None
        assert ResourceConfigService._default_config_id is None

    def test_delete_config_not_found(self):
        with pytest.raises(ValueError):
            ResourceConfigService.delete_config("nonexistent")

    def test_reset(self):
        ResourceConfigService.create_config(
            tenant_id="tenant_1", level=ResourceLevel.MEDIUM, config_id="cfg_1"
        )
        ResourceConfigService.reset()
        assert len(ResourceConfigService._configs) == 0
        assert len(ResourceConfigService._bindings) == 0
        assert ResourceConfigService._default_config_id is None
