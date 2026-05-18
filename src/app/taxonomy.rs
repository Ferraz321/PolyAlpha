pub fn print_taxonomy() {
    println!(
        r#"smart_money_tier:
  core_smart_money          strictest tier, high sample, high PnL, diversified edge
  candidate_smart_money     good smart-money candidate, worth tracking
  watchlist                 interesting but has risk flags
  not_smart_money           noise, one-shot, unprofitable, or too early

primary_tag:
  stable_alpha_wallet       preferred target: repeatable positive expectancy
  information_edge_wallet   low-frequency but high-accuracy information edge
  stat_arb_market_maker_bot high-frequency market-making/stat-arb account
  swing_trader              high profit/loss ratio directional trader
  one_shot_whale            profitable but dominated by one market
  small_sample_noise        not enough evidence yet
  high_volume_noise         high volume without realized edge
  unprofitable_trader       negative realized PnL
  unclassified              does not match a defined profile yet

default matched pool:
  includes stable alpha, information edge, stat-arb/market-maker, swing trader,
  plus core/candidate/watchlist smart-money tiers. It does not require the
  single strict passed_funnel flag.

profile config:
  account type rules live under config/account_types/*.json. Add a new JSON file
  there to define another strategy family or judgment mechanism."#
    );
}
