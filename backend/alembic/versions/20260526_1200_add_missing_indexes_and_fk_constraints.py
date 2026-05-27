"""add missing database indexes and FK constraints

Revision ID: 20260526_1200
Revises: 0627f60b49ad
Create Date: 2026-05-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260526_1200'
down_revision = '0627f60b49ad'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================================================
    # MISSING INDEXES ON FOREIGN KEY COLUMNS
    # ========================================================================

    # ---- users ----
    op.create_index(
        op.f('ix_users_role_id'), 'users', ['role_id'], unique=False,
        postgresql_where=sa.text('role_id IS NOT NULL'),
    )

    # ---- query_history ----
    op.create_index(
        op.f('ix_query_history_user_id'), 'query_history', ['user_id'], unique=False,
    )
    op.create_index(
        op.f('ix_query_history_data_source_id'), 'query_history', ['data_source_id'], unique=False,
        postgresql_where=sa.text('data_source_id IS NOT NULL'),
    )
    op.create_index(
        op.f('ix_query_history_created_at'), 'query_history', ['created_at'], unique=False,
    )

    # ---- templates ----
    op.create_index(
        op.f('ix_templates_created_by'), 'templates', ['created_by'], unique=False,
    )
    op.create_index(
        op.f('ix_templates_created_at'), 'templates', ['created_at'], unique=False,
    )

    # ---- template_versions ----
    op.create_index(
        op.f('ix_template_versions_template_id'), 'template_versions', ['template_id'], unique=False,
    )
    op.create_index(
        op.f('ix_template_versions_created_by'), 'template_versions', ['created_by'], unique=False,
    )

    # ---- template_shares ----
    op.create_index(
        op.f('ix_template_shares_shared_by'), 'template_shares', ['shared_by'], unique=False,
    )

    # ---- export_tasks ----
    op.create_index(
        op.f('ix_export_tasks_user_id'), 'export_tasks', ['user_id'], unique=False,
    )
    op.create_index(
        op.f('ix_export_tasks_status'), 'export_tasks', ['status'], unique=False,
    )
    op.create_index(
        op.f('ix_export_tasks_created_at'), 'export_tasks', ['created_at'], unique=False,
    )

    # ---- data_sources ----
    op.create_index(
        op.f('ix_data_sources_created_by'), 'data_sources', ['created_by'], unique=False,
        postgresql_where=sa.text('created_by IS NOT NULL'),
    )
    op.create_index(
        op.f('ix_data_sources_proxy_server_id'), 'data_sources', ['proxy_server_id'], unique=False,
        postgresql_where=sa.text('proxy_server_id IS NOT NULL'),
    )
    op.create_index(
        op.f('ix_data_sources_is_active'), 'data_sources', ['is_active'], unique=False,
    )

    # ---- proxy_servers ----
    op.create_index(
        op.f('ix_proxy_servers_created_by'), 'proxy_servers', ['created_by'], unique=False,
        postgresql_where=sa.text('created_by IS NOT NULL'),
    )

    # ---- menus ----
    op.create_index(
        op.f('ix_menus_parent_id'), 'menus', ['parent_id'], unique=False,
        postgresql_where=sa.text('parent_id IS NOT NULL'),
    )
    op.create_index(
        op.f('ix_menus_template_id'), 'menus', ['template_id'], unique=False,
        postgresql_where=sa.text('template_id IS NOT NULL'),
    )

    # ---- scheduled_reports ----
    op.create_index(
        op.f('ix_scheduled_reports_template_id'), 'scheduled_reports', ['template_id'], unique=False,
    )
    op.create_index(
        op.f('ix_scheduled_reports_data_source_id'), 'scheduled_reports', ['data_source_id'], unique=False,
        postgresql_where=sa.text('data_source_id IS NOT NULL'),
    )
    op.create_index(
        op.f('ix_scheduled_reports_created_by'), 'scheduled_reports', ['created_by'], unique=False,
    )
    op.create_index(
        op.f('ix_scheduled_reports_created_at'), 'scheduled_reports', ['created_at'], unique=False,
    )

    # ---- report_deliveries ----
    op.create_index(
        op.f('ix_report_deliveries_status'), 'report_deliveries', ['status'], unique=False,
    )

    # ---- audit_logs ----
    op.create_index(
        op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False,
    )
    op.create_index(
        op.f('ix_audit_logs_resource_id'), 'audit_logs', ['resource_id'], unique=False,
    )

    # ---- task_alerts ----
    op.create_index(
        op.f('ix_task_alerts_task_type'), 'task_alerts', ['task_type'], unique=False,
    )
    op.create_index(
        op.f('ix_task_alerts_status'), 'task_alerts', ['status'], unique=False,
    )
    op.create_index(
        op.f('ix_task_alerts_created_at'), 'task_alerts', ['created_at'], unique=False,
    )

    # ---- forecast_history (no actual FK constraint, but queried by these) ----
    op.create_index(
        op.f('ix_forecast_history_data_source_id'), 'forecast_history', ['data_source_id'], unique=False,
    )
    op.create_index(
        op.f('ix_forecast_history_created_by'), 'forecast_history', ['created_by'], unique=False,
        postgresql_where=sa.text('created_by IS NOT NULL'),
    )
    op.create_index(
        op.f('ix_forecast_history_status'), 'forecast_history', ['status'], unique=False,
    )

    # ---- prediction_results ----
    op.create_index(
        op.f('ix_prediction_results_data_source_id'), 'prediction_results', ['data_source_id'], unique=False,
    )
    op.create_index(
        op.f('ix_prediction_results_store_code'), 'prediction_results', ['store_code'], unique=False,
    )
    op.create_index(
        op.f('ix_prediction_results_matnr'), 'prediction_results', ['matnr'], unique=False,
    )
    op.create_index(
        op.f('ix_prediction_results_forecast_date'), 'prediction_results', ['forecast_date'], unique=False,
    )

    # ---- prediction_models ----
    op.create_index(
        op.f('ix_prediction_models_data_source_id'), 'prediction_models', ['data_source_id'], unique=False,
    )
    op.create_index(
        op.f('ix_prediction_models_status'), 'prediction_models', ['status'], unique=False,
    )
    op.create_index(
        op.f('ix_prediction_models_created_by'), 'prediction_models', ['created_by'], unique=False,
        postgresql_where=sa.text('created_by IS NOT NULL'),
    )

    # ========================================================================
    # COMPOSITE INDEXES FOR COMMON QUERY PATTERNS
    # ========================================================================

    # query_history: filter by user + order by date (user's query history page)
    op.create_index(
        'ix_query_history_user_created', 'query_history', ['user_id', 'created_at'], unique=False,
    )
    # query_history: filter by data_source + order by date
    op.create_index(
        'ix_query_history_ds_created', 'query_history', ['data_source_id', 'created_at'], unique=False,
    )

    # templates: list by creator, most recent first
    op.create_index(
        'ix_templates_creator_created', 'templates', ['created_by', 'created_at'], unique=False,
    )

    # template_versions: versions for a template ordered by version
    op.create_index(
        'ix_template_versions_template_version', 'template_versions', ['template_id', 'version'], unique=False,
    )

    # template_shares: look up what's shared with a user
    op.create_index(
        'ix_template_shares_user_template', 'template_shares', ['user_id', 'template_id'], unique=False,
    )

    # export_tasks: filter by user + status + date
    op.create_index(
        'ix_export_tasks_user_status', 'export_tasks', ['user_id', 'status'], unique=False,
    )

    # data_sources: filter active sources by creator
    op.create_index(
        'ix_data_sources_active_creator', 'data_sources', ['is_active', 'created_by'], unique=False,
    )

    # scheduled_reports: filter enabled reports by next run
    # (already has ix_scheduled_reports_enabled_next)

    # report_deliveries: filter by status
    op.create_index(
        'ix_report_delivery_status_generated', 'report_deliveries', ['status', 'generated_at'], unique=False,
    )

    # audit_logs: user action timeline
    op.create_index(
        'ix_audit_logs_user_action_created', 'audit_logs', ['user_id', 'action', 'created_at'], unique=False,
    )
    # audit_logs: resource type + resource id lookup
    op.create_index(
        'ix_audit_logs_resource_type_id', 'audit_logs', ['resource_type', 'resource_id'], unique=False,
    )

    # task_alerts: filter by user + status
    op.create_index(
        'ix_task_alerts_user_status', 'task_alerts', ['user_id', 'status'], unique=False,
    )
    # task_alerts: filter by task type + status
    op.create_index(
        'ix_task_alerts_type_status', 'task_alerts', ['task_type', 'status'], unique=False,
    )

    # forecast_history: data source + model usage tracking
    op.create_index(
        'ix_forecast_history_ds_status', 'forecast_history', ['data_source_id', 'status'], unique=False,
    )

    # prediction_results: store + product + date (lookup)
    op.create_index(
        'ix_prediction_results_store_matnr_date', 'prediction_results',
        ['store_code', 'matnr', 'forecast_date'], unique=False,
    )
    # prediction_results: model + store lookups
    op.create_index(
        'ix_prediction_results_model_ds', 'prediction_results', ['model_id', 'data_source_id'], unique=False,
    )

    # prediction_models: active models by data source
    op.create_index(
        'ix_prediction_models_ds_status', 'prediction_models', ['data_source_id', 'status'], unique=False,
    )

    # ========================================================================
    # MISSING FK CONSTRAINTS
    # ========================================================================

    # The following tables use plain integer columns that logically reference
    # other tables but lack actual FK constraints.  These are added as
    # "soft" FKs (no VALIDATE) to avoid locking large tables.
    #
    # NOTE: We use `batch=False` to ensure PostgreSQL compatibility with
    #       constraints outside of batch mode.

    # forecast_history.data_source_id → data_sources.id
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_forecast_history_data_source') THEN "
        "ALTER TABLE forecast_history ADD CONSTRAINT fk_forecast_history_data_source "
        "FOREIGN KEY (data_source_id) REFERENCES data_sources(id) NOT VALID; "
        "END IF; "
        "END $$;"
    )

    # prediction_models.data_source_id → data_sources.id
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_prediction_models_data_source') THEN "
        "ALTER TABLE prediction_models ADD CONSTRAINT fk_prediction_models_data_source "
        "FOREIGN KEY (data_source_id) REFERENCES data_sources(id) NOT VALID; "
        "END IF; "
        "END $$;"
    )

    # prediction_results.data_source_id → data_sources.id
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_prediction_results_data_source') THEN "
        "ALTER TABLE prediction_results ADD CONSTRAINT fk_prediction_results_data_source "
        "FOREIGN KEY (data_source_id) REFERENCES data_sources(id) NOT VALID; "
        "END IF; "
        "END $$;"
    )

    # prediction_results.model_id → prediction_models.id
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_prediction_results_model') THEN "
        "ALTER TABLE prediction_results ADD CONSTRAINT fk_prediction_results_model "
        "FOREIGN KEY (model_id) REFERENCES prediction_models(id) NOT VALID; "
        "END IF; "
        "END $$;"
    )

    # task_alerts.user_id → users.id
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_task_alerts_user') THEN "
        "ALTER TABLE task_alerts ADD CONSTRAINT fk_task_alerts_user "
        "FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID; "
        "END IF; "
        "END $$;"
    )

    # forecast_history.created_by → users.id
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_forecast_history_created_by') THEN "
        "ALTER TABLE forecast_history ADD CONSTRAINT fk_forecast_history_created_by "
        "FOREIGN KEY (created_by) REFERENCES users(id) NOT VALID; "
        "END IF; "
        "END $$;"
    )


def downgrade() -> None:
    # ========================================================================
    # DROP ADDED FK CONSTRAINTS
    # ========================================================================
    op.execute("ALTER TABLE forecast_history DROP CONSTRAINT IF EXISTS fk_forecast_history_created_by")
    op.execute("ALTER TABLE task_alerts DROP CONSTRAINT IF EXISTS fk_task_alerts_user")
    op.execute("ALTER TABLE prediction_results DROP CONSTRAINT IF EXISTS fk_prediction_results_model")
    op.execute("ALTER TABLE prediction_results DROP CONSTRAINT IF EXISTS fk_prediction_results_data_source")
    op.execute("ALTER TABLE prediction_models DROP CONSTRAINT IF EXISTS fk_prediction_models_data_source")
    op.execute("ALTER TABLE forecast_history DROP CONSTRAINT IF EXISTS fk_forecast_history_data_source")

    # ========================================================================
    # DROP COMPOSITE INDEXES
    # ========================================================================
    op.drop_index('ix_prediction_models_ds_status', table_name='prediction_models')
    op.drop_index('ix_prediction_results_model_ds', table_name='prediction_results')
    op.drop_index('ix_prediction_results_store_matnr_date', table_name='prediction_results')
    op.drop_index('ix_forecast_history_ds_status', table_name='forecast_history')
    op.drop_index('ix_task_alerts_type_status', table_name='task_alerts')
    op.drop_index('ix_task_alerts_user_status', table_name='task_alerts')
    op.drop_index('ix_audit_logs_resource_type_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_action_created', table_name='audit_logs')
    op.drop_index('ix_report_delivery_status_generated', table_name='report_deliveries')
    op.drop_index('ix_data_sources_active_creator', table_name='data_sources')
    op.drop_index('ix_export_tasks_user_status', table_name='export_tasks')
    op.drop_index('ix_template_shares_user_template', table_name='template_shares')
    op.drop_index('ix_template_versions_template_version', table_name='template_versions')
    op.drop_index('ix_templates_creator_created', table_name='templates')
    op.drop_index('ix_query_history_ds_created', table_name='query_history')
    op.drop_index('ix_query_history_user_created', table_name='query_history')

    # ========================================================================
    # DROP SINGLE-COLUMN INDEXES
    # ========================================================================
    op.drop_index(op.f('ix_prediction_models_created_by'), table_name='prediction_models')
    op.drop_index(op.f('ix_prediction_models_status'), table_name='prediction_models')
    op.drop_index(op.f('ix_prediction_models_data_source_id'), table_name='prediction_models')
    op.drop_index(op.f('ix_prediction_results_forecast_date'), table_name='prediction_results')
    op.drop_index(op.f('ix_prediction_results_matnr'), table_name='prediction_results')
    op.drop_index(op.f('ix_prediction_results_store_code'), table_name='prediction_results')
    op.drop_index(op.f('ix_prediction_results_data_source_id'), table_name='prediction_results')
    op.drop_index(op.f('ix_forecast_history_status'), table_name='forecast_history')
    op.drop_index(op.f('ix_forecast_history_created_by'), table_name='forecast_history')
    op.drop_index(op.f('ix_forecast_history_data_source_id'), table_name='forecast_history')
    op.drop_index(op.f('ix_task_alerts_created_at'), table_name='task_alerts')
    op.drop_index(op.f('ix_task_alerts_status'), table_name='task_alerts')
    op.drop_index(op.f('ix_task_alerts_task_type'), table_name='task_alerts')
    op.drop_index(op.f('ix_audit_logs_resource_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_report_deliveries_status'), table_name='report_deliveries')
    op.drop_index(op.f('ix_scheduled_reports_created_at'), table_name='scheduled_reports')
    op.drop_index(op.f('ix_scheduled_reports_created_by'), table_name='scheduled_reports')
    op.drop_index(op.f('ix_scheduled_reports_data_source_id'), table_name='scheduled_reports')
    op.drop_index(op.f('ix_scheduled_reports_template_id'), table_name='scheduled_reports')
    op.drop_index(op.f('ix_menus_template_id'), table_name='menus')
    op.drop_index(op.f('ix_menus_parent_id'), table_name='menus')
    op.drop_index(op.f('ix_proxy_servers_created_by'), table_name='proxy_servers')
    op.drop_index(op.f('ix_data_sources_is_active'), table_name='data_sources')
    op.drop_index(op.f('ix_data_sources_proxy_server_id'), table_name='data_sources')
    op.drop_index(op.f('ix_data_sources_created_by'), table_name='data_sources')
    op.drop_index(op.f('ix_export_tasks_created_at'), table_name='export_tasks')
    op.drop_index(op.f('ix_export_tasks_status'), table_name='export_tasks')
    op.drop_index(op.f('ix_export_tasks_user_id'), table_name='export_tasks')
    op.drop_index(op.f('ix_template_shares_shared_by'), table_name='template_shares')
    op.drop_index(op.f('ix_template_versions_created_by'), table_name='template_versions')
    op.drop_index(op.f('ix_template_versions_template_id'), table_name='template_versions')
    op.drop_index(op.f('ix_templates_created_at'), table_name='templates')
    op.drop_index(op.f('ix_templates_created_by'), table_name='templates')
    op.drop_index(op.f('ix_query_history_created_at'), table_name='query_history')
    op.drop_index(op.f('ix_query_history_data_source_id'), table_name='query_history')
    op.drop_index(op.f('ix_query_history_user_id'), table_name='query_history')
    op.drop_index(op.f('ix_users_role_id'), table_name='users')
