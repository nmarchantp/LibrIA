"""Static and unit acceptance checks for the definitive provider cutover."""
import inspect
import unittest
from pathlib import Path

from app.core.config import Settings
from app.modules.analytics.gemini_worker import process_one

APPS=Path(__file__).resolve().parents[2]
REPO=APPS.parent


class Stage6CutoverTest(unittest.TestCase):
    def test_no_active_local_provider_transport_or_installer(self):
        roots=[APPS/"backend/app",APPS/"backend/scripts",REPO/"scripts"]
        forbidden=("localhost:11434","127.0.0.1:11434","/api/chat","/api/tags","ollama serve","ollama pull")
        for root in roots:
            for path in root.rglob("*"):
                if not path.is_file() or "legacy" in path.parts or path.suffix not in {".py",".ps1",".cmd"}:
                    continue
                content=path.read_text(encoding="utf-8").casefold()
                for marker in forbidden:
                    self.assertNotIn(marker,content,f"{marker} remains active in {path}")

    def test_api_does_not_spawn_workers_or_scheduler(self):
        source=(APPS/"backend/app/main.py").read_text(encoding="utf-8")
        self.assertNotIn("create_task",source)
        self.assertNotIn("worker_loop",source)
        self.assertNotIn("daily_scheduler",source)

    def test_real_worker_requires_two_explicit_switches(self):
        settings=Settings(_env_file=None)
        with self.assertRaises(RuntimeError):
            process_one(settings=settings)

    def test_pricing_is_nonzero_and_bound_to_model(self):
        settings=Settings(_env_file=None)
        self.assertEqual(settings.gemini_model,"gemini-3.5-flash-lite")
        self.assertEqual(settings.ai_pricing_model,settings.gemini_model)
        self.assertGreater(settings.ai_input_cost_per_million_usd,0)
        self.assertGreater(settings.ai_output_cost_per_million_usd,0)
        self.assertGreater(settings.ai_monthly_budget_usd,0)
        with self.assertRaises(ValueError):
            Settings(_env_file=None,gemini_model="otro-modelo")

    def test_budget_accounts_inflight_retries_calls_and_fragments(self):
        source=inspect.getsource(__import__("app.modules.analytics.gemini_worker",fromlist=["*"]))
        for marker in ("monthly_budget_snapshot","gemini-monthly-budget","monthly_budget_exhausted",
                       "request_count=budget.calls","context_fragments=budget.fragments"):
            self.assertIn(marker,source)

    def test_migration_chain_is_forward_only(self):
        migration=(APPS/"backend/migrations/versions/0052_ai_usage_call_accounting.py").read_text(encoding="utf-8")
        self.assertIn('down_revision = "0051_sessions_controlled_ai"',migration)
        self.assertIn("request_count",migration)
        self.assertIn("context_fragments",migration)
        self.assertIn("SET DEFAULT 'gemini'",migration)

    def test_compose_has_separate_single_purpose_services(self):
        compose=(REPO/"compose.yaml").read_text(encoding="utf-8")
        for service in ("db:","migrate:","schema-check:","api:","scheduler:","gemini-worker:","web:"):
            self.assertIn(service,compose)
        self.assertIn('profiles: ["gemini"]',compose)
        self.assertIn('profiles: ["migration"]',compose)
        self.assertIn('["python", "-m", "alembic", "current", "--check-heads"]',compose)
        self.assertNotIn("gpu",compose.casefold())

    def test_windows_preflight_is_read_only_and_legacy_setup_is_safe(self):
        runner=(REPO/"scripts/run-local.ps1").read_text(encoding="utf-8")
        preflight=runner[runner.index("if ($PreflightOnly)"):runner.index("Write-Host 'Comprobando dependencias Python")]
        for forbidden in ("Start-Process","pip install","npm ci","prepare-ai.ps1","alembic upgrade"):
            self.assertNotIn(forbidden,preflight)
        self.assertIn("alembic current --check-heads",preflight)
        self.assertIn("return",preflight)

        legacy=(REPO/"scripts/setup-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("setup-windows-safe.ps1",legacy)
        for forbidden in ("CREATE DATABASE","ALTER ROLE","purge_non_spanish","Set-Content"):
            self.assertNotIn(forbidden,legacy)

        selector=(REPO/"scripts/configure-database.ps1").read_text(encoding="utf-8")
        self.assertNotIn("55432",selector)
        self.assertNotIn("libria_test",selector)

    def test_frontend_polls_owner_jobs_and_never_generates_on_mount(self):
        recommendations=(APPS/"web/src/pages/RecommendationsPage.jsx").read_text(encoding="utf-8")
        adaptive=(APPS/"web/src/components/AdaptiveAnalysis.jsx").read_text(encoding="utf-8")
        self.assertIn('async function requestRecommendations()',recommendations)
        self.assertIn("/analytics/me/recommendations/sync",recommendations)
        mount= recommendations[recommendations.index('  useEffect(() => {'):recommendations.index('  const items =')]
        self.assertNotIn("method: 'POST'",mount)
        self.assertIn("setInterval",adaptive)
        self.assertIn("clearInterval",adaptive)
        self.assertIn("/me/ai/profile/refresh",adaptive)
        self.assertIn("`${base}/refresh`",adaptive)
        self.assertNotIn("canGenerate={user?.role === 'admin'}",adaptive)

    def test_privacy_and_controlled_test_are_documented(self):
        document=(REPO/"docs/gemini-stage6-production-readiness.md").read_text(encoding="utf-8")
        for marker in ("nivel gratuito","nivel pagado","55 días","USD 0,0098",
                       "datos ficticios","GEMINI_PAID_SERVICE_CONFIRMED"):
            self.assertIn(marker,document)


if __name__ == "__main__":
    unittest.main()
