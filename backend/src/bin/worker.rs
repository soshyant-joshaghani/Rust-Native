use rust_native::core::config::Settings;
use rust_native::core::init_tracing;
use rust_native::core::jobs::run_worker;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing();
    let settings = Settings::from_env()?;
    run_worker(&settings.redis_url()).await
}
