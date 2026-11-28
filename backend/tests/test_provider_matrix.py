import os


def _clean_purge_env():
    for key in list(os.environ.keys()):
        if key.startswith(('SCHOLARZONE_', 'EXPECTED_', 'GPG_', 'RESTORE_TEST_', 'TEST_DATABASE_', 'ARTIFACT_', 'DURABLE_', 'AZURE_')):
            del os.environ[key]


def _base_gate4_env():
    os.environ['SCHOLARZONE_DATABASE_URL_BACKUP'] = 'postgresql://backup@localhost/db'
    os.environ['GPG_RECIPIENT'] = 'test@example.com'
    os.environ['GPG_EXPECTED_FINGERPRINT'] = 'A' * 40
    os.environ['RESTORE_TEST_PGHOST'] = 'localhost'
    os.environ['RESTORE_TEST_PGPORT'] = '5432'
    os.environ['RESTORE_TEST_PGUSER'] = 'test'
    os.environ['RESTORE_TEST_PGPASSWORD'] = 'test'
    os.environ['EXPECTED_NEON_PROJECT_ID'] = 'proj'
    os.environ['EXPECTED_NEON_BRANCH_ID'] = 'br'
    os.environ['EXPECTED_NEON_BRANCH_NAME'] = 'main'
    os.environ['EXPECTED_DATABASE_NAME'] = 'db'
    os.environ['EXPECTED_DATABASE_HOST'] = 'localhost'


def test_provider_azure_valid_without_secret():
    from app.services.purge_preflight.config import PreflightConfig
    _clean_purge_env()
    _base_gate4_env()
    os.environ['DURABLE_STORAGE_PROVIDER'] = 'azure'
    os.environ['DURABLE_STORAGE_BUCKET'] = 'container'
    os.environ['DURABLE_STORAGE_REGION'] = 'accountname'
    os.environ['DURABLE_STORAGE_CREDENTIAL'] = 'storageaccount'
    config = PreflightConfig.from_env(gates_to_run={'gate4'})
    assert config.durable_storage.provider == 'azure'
    assert config.durable_storage.credential_secret == ''


def test_provider_azure_missing_credential():
    from app.services.purge_preflight.config import PreflightConfig
    _clean_purge_env()
    _base_gate4_env()
    os.environ['DURABLE_STORAGE_PROVIDER'] = 'azure'
    os.environ['DURABLE_STORAGE_BUCKET'] = 'container'
    os.environ['DURABLE_STORAGE_REGION'] = 'accountname'
    try:
        PreflightConfig.from_env(gates_to_run={'gate4'})
        assert False, "Should require credential for azure"
    except ValueError as e:
        assert "DURABLE_STORAGE_CREDENTIAL" in str(e)


def test_provider_azure_missing_bucket():
    from app.services.purge_preflight.config import PreflightConfig
    _clean_purge_env()
    _base_gate4_env()
    os.environ['DURABLE_STORAGE_PROVIDER'] = 'azure'
    os.environ['DURABLE_STORAGE_REGION'] = 'accountname'
    os.environ['DURABLE_STORAGE_CREDENTIAL'] = 'storageaccount'
    try:
        PreflightConfig.from_env(gates_to_run={'gate4'})
        assert False, "Should require bucket for azure"
    except ValueError as e:
        assert "DURABLE_STORAGE_BUCKET" in str(e)


def test_provider_azure_missing_region():
    from app.services.purge_preflight.config import PreflightConfig
    _clean_purge_env()
    _base_gate4_env()
    os.environ['DURABLE_STORAGE_PROVIDER'] = 'azure'
    os.environ['DURABLE_STORAGE_BUCKET'] = 'container'
    os.environ['DURABLE_STORAGE_CREDENTIAL'] = 'storageaccount'
    try:
        PreflightConfig.from_env(gates_to_run={'gate4'})
        assert False, "Should require region for azure"
    except ValueError as e:
        assert "DURABLE_STORAGE_REGION" in str(e)


def test_provider_invalid_rejected():
    from app.services.purge_preflight.config import PreflightConfig
    _clean_purge_env()
    _base_gate4_env()
    os.environ['DURABLE_STORAGE_PROVIDER'] = 'ftp'
    os.environ['DURABLE_STORAGE_BUCKET'] = 'bucket'
    os.environ['DURABLE_STORAGE_REGION'] = 'us'
    os.environ['DURABLE_STORAGE_CREDENTIAL'] = 'cred'
    try:
        PreflightConfig.from_env(gates_to_run={'gate4'})
        assert False, "Should reject invalid provider"
    except ValueError as e:
        assert "must be one of" in str(e)


def test_provider_azure_unused_secret_does_not_become_required():
    from app.services.purge_preflight.config import PreflightConfig
    _clean_purge_env()
    _base_gate4_env()
    os.environ['DURABLE_STORAGE_PROVIDER'] = 'azure'
    os.environ['DURABLE_STORAGE_BUCKET'] = 'container'
    os.environ['DURABLE_STORAGE_REGION'] = 'accountname'
    os.environ['DURABLE_STORAGE_CREDENTIAL'] = 'storageaccount'
    # secret absent -> still ok
    config = PreflightConfig.from_env(gates_to_run={'gate4'})
    assert config.durable_storage.provider == 'azure'


def test_provider_azure_allows_unused_secret_value():
    from app.services.purge_preflight.config import PreflightConfig
    _clean_purge_env()
    _base_gate4_env()
    os.environ['DURABLE_STORAGE_PROVIDER'] = 'azure'
    os.environ['DURABLE_STORAGE_BUCKET'] = 'container'
    os.environ['DURABLE_STORAGE_REGION'] = 'accountname'
    os.environ['DURABLE_STORAGE_CREDENTIAL'] = 'storageaccount'
    os.environ['DURABLE_STORAGE_CREDENTIAL_SECRET'] = 'ignored'
    config = PreflightConfig.from_env(gates_to_run={'gate4'})
    assert config.durable_storage.provider == 'azure'


def test_provider_s3_requires_secret():
    from app.services.purge_preflight.config import PreflightConfig
    _clean_purge_env()
    _base_gate4_env()
    os.environ['DURABLE_STORAGE_PROVIDER'] = 's3'
    os.environ['DURABLE_STORAGE_BUCKET'] = 'bucket'
    os.environ['DURABLE_STORAGE_REGION'] = 'us-east-1'
    os.environ['DURABLE_STORAGE_CREDENTIAL'] = 'AKIAEXAMPLE'
    try:
        PreflightConfig.from_env(gates_to_run={'gate4'})
        assert False, "Should require credential secret for s3"
    except ValueError as e:
        assert "DURABLE_STORAGE_CREDENTIAL_SECRET" in str(e)


def test_provider_gcs_does_not_require_secret():
    from app.services.purge_preflight.config import PreflightConfig
    _clean_purge_env()
    _base_gate4_env()
    os.environ['DURABLE_STORAGE_PROVIDER'] = 'gcs'
    os.environ['DURABLE_STORAGE_BUCKET'] = 'bucket'
    os.environ['DURABLE_STORAGE_REGION'] = 'us'
    os.environ['DURABLE_STORAGE_CREDENTIAL'] = '/path/sa.json'
    config = PreflightConfig.from_env(gates_to_run={'gate4'})
    assert config.durable_storage.provider == 'gcs'
    assert config.durable_storage.credential_secret == ''


def test_provider_no_cross_provider_fallback_azure_missing_credential_not_s3():
    # Ensure azure missing credential is not satisfied by s3-style secret
    from app.services.purge_preflight.config import PreflightConfig
    _clean_purge_env()
    _base_gate4_env()
    os.environ['DURABLE_STORAGE_PROVIDER'] = 'azure'
    os.environ['DURABLE_STORAGE_BUCKET'] = 'container'
    os.environ['DURABLE_STORAGE_REGION'] = 'accountname'
    os.environ['DURABLE_STORAGE_CREDENTIAL_SECRET'] = 'AKIASECRET'
    try:
        PreflightConfig.from_env(gates_to_run={'gate4'})
        assert False, "Should require credential even if secret present"
    except ValueError as e:
        assert "DURABLE_STORAGE_CREDENTIAL" in str(e)


def test_host_normalization_case_and_trailing_dot():
    from app.services.purge_preflight.database import DatabaseAccessor, DatabaseConfig, DatabaseIdentity
    cfg = DatabaseConfig(expected_database_name='db', expected_neon_project_id='p',
                          expected_neon_branch_id='b', expected_neon_branch_name='main',
                          expected_database_host='Example.COM.')
    accessor = DatabaseAccessor(cfg)
    identity = DatabaseIdentity(
        database_name='db', server_version='v', current_user='u',
        server_address='example.com', server_port=5432, connection_host=None,
        neon_project_id='p', neon_branch_id='b', neon_branch_name='main',
        is_read_only=True, in_transaction=False,
    )
    errors = accessor.validate_identity(identity)
    assert errors == [], errors


def test_host_normalization_mismatch():
    from app.services.purge_preflight.database import DatabaseAccessor, DatabaseConfig, DatabaseIdentity
    cfg = DatabaseConfig(expected_database_name='db', expected_neon_project_id='p',
                          expected_neon_branch_id='b', expected_neon_branch_name='main',
                          expected_database_host='expected.example.com')
    accessor = DatabaseAccessor(cfg)
    identity = DatabaseIdentity(
        database_name='db', server_version='v', current_user='u',
        server_address='other.example.com', server_port=5432, connection_host=None,
        neon_project_id='p', neon_branch_id='b', neon_branch_name='main',
        is_read_only=True, in_transaction=False,
    )
    errors = accessor.validate_identity(identity)
    assert any('host mismatch' in e.lower() or 'Database host mismatch' in e for e in errors), errors


def test_host_malformed_fails_closed():
    from app.services.purge_preflight.database import DatabaseAccessor, DatabaseConfig, DatabaseIdentity
    cfg = DatabaseConfig(expected_database_name='db', expected_neon_project_id='p',
                          expected_neon_branch_id='b', expected_neon_branch_name='main',
                          expected_database_host='prod.example.com')
    accessor = DatabaseAccessor(cfg)
    identity = DatabaseIdentity(
        database_name='db', server_version='v', current_user='u',
        server_address='prod.example.com.evil.com', server_port=5432, connection_host=None,
        neon_project_id='p', neon_branch_id='b', neon_branch_name='main',
        is_read_only=True, in_transaction=False,
    )
    errors = accessor.validate_identity(identity)
    assert len(errors) > 0, errors


def test_host_missing_observed_fails():
    from app.services.purge_preflight.database import DatabaseAccessor, DatabaseConfig, DatabaseIdentity
    cfg = DatabaseConfig(expected_database_name='db', expected_neon_project_id='p',
                          expected_neon_branch_id='b', expected_neon_branch_name='main',
                          expected_database_host='prod.example.com')
    accessor = DatabaseAccessor(cfg)
    identity = DatabaseIdentity(
        database_name='db', server_version='v', current_user='u',
        server_address=None, server_port=5432, connection_host=None,
        neon_project_id='p', neon_branch_id='b', neon_branch_name='main',
        is_read_only=True, in_transaction=False,
    )
    errors = accessor.validate_identity(identity)
    assert len(errors) > 0, errors
