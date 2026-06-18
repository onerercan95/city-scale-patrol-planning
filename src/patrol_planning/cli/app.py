from pathlib import Path
from time import perf_counter
from typing import Optional

import typer

from patrol_planning.config.models import load_config
from patrol_planning.config.selection import resolve_config_path
from patrol_planning.data.adapters.la_crime import LACrimeAdapter
from patrol_planning.experiments.runner import run_experiments
from patrol_planning.experiments.baseline_comparison import (
    run_baseline_comparison,
)
from patrol_planning.experiments.final_evaluation import run_final_evaluation
from patrol_planning.experiments.success_criteria import (
    assess_success_criteria_from_artifacts,
)
from patrol_planning.output.layout import (
    grouped_data_directory,
    grouped_image_directory,
    html_directory,
    image_directory,
)
from patrol_planning.scenarios.builder import build_scenario as create_scenario
from patrol_planning.scenarios.export import export_poisson_rates, export_scenario
from patrol_planning.solvers.minp.export import export_minp_result
from patrol_planning.solvers.minp.greedy import solve_minp
from patrol_planning.solvers.grafting.dp import solve_grafting
from patrol_planning.solvers.grafting.export import export_grafting_result
from patrol_planning.solvers.maxp.allocation import solve_maxp
from patrol_planning.solvers.maxp.export import export_maxp_result
from patrol_planning.validation.maxp import validate_maxp_result
from patrol_planning.validation.grafting import validate_grafting_result
from patrol_planning.validation.minp import validate_minp_result
from patrol_planning.validation.scenario import validate_scenario
from patrol_planning.visualization.map import build_scenario_map
from patrol_planning.visualization.combined_map import build_combined_map
from patrol_planning.visualization.final_map import build_final_map
from patrol_planning.visualization.maxp_map import build_maxp_map
from patrol_planning.visualization.minp_map import build_minp_map
from patrol_planning.visualization.run_metrics import build_run_metric_images
from patrol_planning.visualization.coverage_explanation import (
    build_coverage_explanation_plot,
)


app = typer.Typer(
    help="Build offline city-scale patrol-planning scenarios from historical data.",
    no_args_is_help=True,
)


def _load_selected_config(config_path: Optional[Path]):
    try:
        selected_path = resolve_config_path(config_path)
    except (FileNotFoundError, OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--config") from error
    return load_config(selected_path)


def _export_vfop_summary(scenario, output_directory: Path) -> None:
    from patrol_planning.visualization.vfop_plot import build_vfop_summary

    build_vfop_summary(
        scenario,
        image_directory(output_directory) / "vfop_shift_heatmaps.png",
    )


@app.command("assess-success-criteria")
def assess_success_criteria(
    output_directory: Path = typer.Option(
        ...,
        "--artifacts",
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Artifact directory produced by the full patrol pipeline.",
    ),
    max_seconds: float = typer.Option(60.0, "--max-seconds"),
) -> None:
    """Assess the presentation success criteria from exported artifacts."""
    results = assess_success_criteria_from_artifacts(
        output_directory,
        max_seconds=max_seconds,
    )
    for result in results:
        typer.echo(f"{result.status}: {result.name}")
        typer.echo(f"  Evidence: {result.evidence}")
        if result.limitation:
            typer.echo(f"  Limitation: {result.limitation}")

    if not all(result.passed for result in results):
        raise typer.Exit(code=1)


@app.command("plot-coverage-explanation")
def plot_coverage_explanation(
    artifact_directory: Path = typer.Option(
        ...,
        "--artifacts",
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Artifact directory containing regions, incidents, MinP routes, and coverage CSVs.",
    ),
    output_path: Path = typer.Option(
        None,
        "--output",
        file_okay=True,
        dir_okay=False,
        help="PNG output path. Defaults to coverage_explanation.png in the artifact directory.",
    ),
) -> None:
    """Plot incident coverage links separately from patrol route movement."""
    output = output_path or image_directory(
        artifact_directory
    ) / "coverage_explanation.png"
    build_coverage_explanation_plot(artifact_directory, output)
    typer.echo(f"Coverage explanation plot: {output}")


@app.command("audit-data")
def audit_data(
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        exists=True,
        dir_okay=False,
        help="Config YAML. Defaults to the selection in configs/default.yaml.",
    ),
) -> None:
    """Validate and summarize the configured LA historical slice."""
    config = _load_selected_config(config_path)
    incidents, report = LACrimeAdapter(config.data).load()
    typer.echo(f"Source rows scanned: {report.source_rows:,}")
    typer.echo(f"Rows matching area/date: {report.selected_rows:,}")
    typer.echo(f"Valid normalized incidents: {report.output_rows:,}")
    typer.echo(f"Invalid coordinates: {report.invalid_coordinates:,}")
    typer.echo(f"Invalid dates/times: {report.invalid_dates + report.invalid_times:,}")
    typer.echo(f"Duplicate IDs: {report.duplicate_ids:,}")
    if incidents:
        typer.echo(
            "Normalized range: "
            f"{incidents[0].occurred_at.isoformat()} to "
            f"{incidents[-1].occurred_at.isoformat()}"
        )


@app.command("build-scenario")
def build_scenario(
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        exists=True,
        dir_okay=False,
        help="Config YAML. Defaults to the selection in configs/default.yaml.",
    ),
) -> None:
    """Build and export the configured replay or Poisson scenario."""
    config = _load_selected_config(config_path)
    incidents, report = LACrimeAdapter(config.data).load()
    result = create_scenario(config, incidents)
    scenario_report = validate_scenario(result.scenario)
    if not scenario_report.valid:
        typer.echo(
            f"Scenario validation failed: {'; '.join(scenario_report.errors[:5])}",
            err=True,
        )
        raise typer.Exit(code=1)
    export_scenario(
        result.scenario,
        report,
        scenario_report,
        config.output.directory,
    )
    export_poisson_rates(result.poisson_rates, config.output.directory)
    build_scenario_map(
        result.scenario,
        html_directory(config.output.directory) / "scenario_map.html",
    )
    _export_vfop_summary(result.scenario, config.output.directory)

    typer.echo(f"Scenario: {result.scenario.name}")
    typer.echo(f"Historical incidents used: {len(incidents):,}")
    typer.echo(f"Planning-day incidents: {len(result.scenario.incidents):,}")
    typer.echo(f"Grid regions: {len(result.scenario.regions):,}")
    typer.echo(f"Officers configured: {len(result.scenario.officers):,}")
    typer.echo("Scenario validation: passed")
    typer.echo(f"Output: {config.output.directory}")


@app.command("run-minp")
def run_minp(
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        exists=True,
        dir_okay=False,
        help="Config YAML. Defaults to the selection in configs/default.yaml.",
    ),
) -> None:
    """Build a scenario and greedily find incident-covering MinP routes."""
    config = _load_selected_config(config_path)
    incidents, data_report = LACrimeAdapter(config.data).load()
    build_result = create_scenario(config, incidents)
    scenario = build_result.scenario
    scenario_report = validate_scenario(scenario)
    if not scenario_report.valid:
        typer.echo(
            f"Scenario validation failed: {'; '.join(scenario_report.errors[:5])}",
            err=True,
        )
        raise typer.Exit(code=1)

    export_scenario(
        scenario,
        data_report,
        scenario_report,
        config.output.directory,
    )
    export_poisson_rates(build_result.poisson_rates, config.output.directory)
    result = solve_minp(scenario, max_labels=config.minp.max_labels)
    minp_report = validate_minp_result(scenario, result)
    export_minp_result(result, minp_report, config.output.directory)
    build_minp_map(
        scenario,
        result,
        html_directory(config.output.directory) / "minp_routes_map.html",
    )
    _export_vfop_summary(scenario, config.output.directory)

    typer.echo(f"Scenario: {scenario.name}")
    typer.echo(f"Planning incidents: {len(scenario.incidents):,}")
    typer.echo(f"Selected MinP officers: {result.selected_officer_count:,}")
    typer.echo(f"Covered incidents: {minp_report.covered_request_count:,}")
    typer.echo(f"Uncovered incidents: {minp_report.uncovered_request_count:,}")
    typer.echo(f"MinP feasible: {'yes' if result.feasible else 'no'}")
    typer.echo(
        "MinP label cap reached: "
        f"{'yes' if result.search_truncated else 'no'} "
        f"({result.truncated_search_count} route searches)"
    )
    typer.echo(f"Independent validation: {'passed' if minp_report.valid else 'failed'}")
    typer.echo(f"Output: {config.output.directory}")
    if not minp_report.valid:
        for error in minp_report.errors[:5]:
            typer.echo(f"- {error}", err=True)
        raise typer.Exit(code=1)


@app.command("run-maxp")
def run_maxp(
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        exists=True,
        dir_okay=False,
        help="Config YAML. Defaults to the selection in configs/default.yaml.",
    ),
) -> None:
    """Run MinP, then maximize visibility with all remaining officers."""
    config = _load_selected_config(config_path)
    incidents, data_report = LACrimeAdapter(config.data).load()
    build_result = create_scenario(config, incidents)
    scenario = build_result.scenario
    scenario_report = validate_scenario(scenario)
    if not scenario_report.valid:
        typer.echo(
            f"Scenario validation failed: {'; '.join(scenario_report.errors[:5])}",
            err=True,
        )
        raise typer.Exit(code=1)
    export_scenario(
        scenario,
        data_report,
        scenario_report,
        config.output.directory,
    )
    export_poisson_rates(build_result.poisson_rates, config.output.directory)

    minp_result = solve_minp(scenario, max_labels=config.minp.max_labels)
    minp_report = validate_minp_result(scenario, minp_result)
    export_minp_result(minp_result, minp_report, config.output.directory)
    if not minp_report.valid or not minp_result.feasible:
        typer.echo("MaxP requires a valid, feasible MinP result.", err=True)
        raise typer.Exit(code=1)

    maxp_result = solve_maxp(
        scenario,
        minp_result,
        cost_scale=config.maxp.cost_scale,
        random_seed=config.scenario.random_seed,
    )
    maxp_report = validate_maxp_result(scenario, minp_result, maxp_result)
    export_maxp_result(maxp_result, maxp_report, config.output.directory)
    build_maxp_map(
        scenario,
        maxp_result,
        html_directory(config.output.directory) / "maxp_routes_map.html",
    )
    build_combined_map(
        scenario,
        minp_result,
        maxp_result,
        html_directory(config.output.directory) / "combined_routes_map.html",
    )
    _export_vfop_summary(scenario, config.output.directory)

    typer.echo(f"Scenario: {scenario.name}")
    typer.echo(f"MinP officers: {minp_result.selected_officer_count:,}")
    typer.echo(f"MaxP officers: {maxp_result.assigned_officer_count:,}")
    typer.echo(
        "MaxP shift allocation: "
        + ", ".join(
            f"shift {shift}={count}"
            for shift, count in sorted(maxp_result.shift_allocation.items())
        )
    )
    typer.echo(f"MinP PVR: {maxp_result.minp_pvr:.3f}")
    typer.echo(f"MaxP PVR: {maxp_result.maxp_pvr:.3f}")
    typer.echo(f"Combined PVR: {maxp_result.combined_pvr:.3f}")
    typer.echo(
        "Paper reference bound 1-alpha: "
        f"{maxp_result.approximation_bound:.3f} "
        "(not independently proven for the adapted pipeline)"
    )
    typer.echo(f"Independent validation: {'passed' if maxp_report.valid else 'failed'}")
    typer.echo(f"Output: {config.output.directory}")
    if not maxp_report.valid:
        for error in maxp_report.errors[:5]:
            typer.echo(f"- {error}", err=True)
        raise typer.Exit(code=1)


@app.command("run")
def run_grafting(
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        exists=True,
        dir_okay=False,
        help="Config YAML. Defaults to the selection in configs/default.yaml.",
    ),
) -> None:
    """Run the full MinP, MaxP, and grafting patrol-planning pipeline."""
    config = _load_selected_config(config_path)
    incidents, data_report = LACrimeAdapter(config.data).load()
    build_result = create_scenario(config, incidents)
    scenario = build_result.scenario
    scenario_report = validate_scenario(scenario)
    if not scenario_report.valid:
        typer.echo("Scenario validation failed.", err=True)
        raise typer.Exit(code=1)
    export_scenario(
        scenario,
        data_report,
        scenario_report,
        config.output.directory,
    )
    export_poisson_rates(build_result.poisson_rates, config.output.directory)

    minp_started = perf_counter()
    minp_result = solve_minp(scenario, max_labels=config.minp.max_labels)
    minp_seconds = perf_counter() - minp_started
    minp_report = validate_minp_result(scenario, minp_result)
    export_minp_result(minp_result, minp_report, config.output.directory)
    if not minp_report.valid or not minp_result.feasible:
        typer.echo("Grafting requires a valid, feasible MinP result.", err=True)
        raise typer.Exit(code=1)

    maxp_started = perf_counter()
    maxp_result = solve_maxp(
        scenario,
        minp_result,
        cost_scale=config.maxp.cost_scale,
        random_seed=config.scenario.random_seed,
    )
    maxp_seconds = perf_counter() - maxp_started
    maxp_report = validate_maxp_result(scenario, minp_result, maxp_result)
    export_maxp_result(maxp_result, maxp_report, config.output.directory)
    if not maxp_report.valid:
        typer.echo("Grafting requires a valid MaxP result.", err=True)
        raise typer.Exit(code=1)

    grafting_started = perf_counter()
    grafting_result = solve_grafting(scenario, minp_result, maxp_result)
    grafting_seconds = perf_counter() - grafting_started
    grafting_report = validate_grafting_result(
        scenario,
        minp_result,
        maxp_result,
        grafting_result,
    )
    export_grafting_result(
        grafting_result,
        grafting_report,
        config.output.directory,
    )
    build_scenario_map(
        scenario,
        html_directory(config.output.directory) / "scenario_map.html",
    )
    build_minp_map(
        scenario,
        minp_result,
        html_directory(config.output.directory) / "minp_routes_map.html",
    )
    build_maxp_map(
        scenario,
        maxp_result,
        html_directory(config.output.directory) / "maxp_routes_map.html",
    )
    build_combined_map(
        scenario,
        minp_result,
        maxp_result,
        html_directory(config.output.directory) / "combined_routes_map.html",
    )
    build_final_map(
        scenario,
        minp_result,
        maxp_result,
        grafting_result,
        html_directory(config.output.directory) / "final_grafted_routes_map.html",
    )
    _export_vfop_summary(scenario, config.output.directory)
    build_run_metric_images(
        scenario,
        minp_result,
        maxp_result,
        grafting_result,
        minp_report,
        grafting_report,
        {
            "minp": minp_seconds,
            "maxp": maxp_seconds,
            "grafting": grafting_seconds,
        },
        image_directory(config.output.directory),
    )

    typer.echo(f"Scenario: {scenario.name}")
    typer.echo(f"MinP officers: {minp_result.selected_officer_count:,}")
    typer.echo(
        "MinP label cap reached: "
        f"{'yes' if minp_result.search_truncated else 'no'} "
        f"({minp_result.truncated_search_count} route searches)"
    )
    typer.echo(f"MaxP officers: {maxp_result.assigned_officer_count:,}")
    typer.echo(f"Free windows processed: {grafting_result.processed_window_count:,}")
    typer.echo(f"Productive graft windows: {grafting_result.productive_window_count:,}")
    typer.echo(f"Added graft visits: {grafting_result.added_visit_count:,}")
    typer.echo(f"Before grafting PVR: {grafting_result.baseline_combined_pvr:.3f}")
    typer.echo(f"After grafting PVR: {grafting_result.grafted_combined_pvr:.3f}")
    typer.echo(f"Grafting gain: {grafting_result.grafting_gain:.3f}")
    typer.echo(
        "Incident coverage preserved: "
        f"{'yes' if grafting_report.incident_coverage_preserved else 'no'}"
    )
    typer.echo(
        f"Independent validation: {'passed' if grafting_report.valid else 'failed'}"
    )
    typer.echo(f"Output: {config.output.directory}")
    if not grafting_report.valid:
        for error in grafting_report.errors[:5]:
            typer.echo(f"- {error}", err=True)
        raise typer.Exit(code=1)


@app.command("run-experiments")
def run_experiment_suite(
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        exists=True,
        dir_okay=False,
        help="Config YAML. Defaults to the selection in configs/default.yaml.",
    ),
) -> None:
    """Run the configured replay-date and officer-count experiment matrix."""
    config = _load_selected_config(config_path)
    from patrol_planning.experiments.plots import build_experiment_charts

    if not config.experiment.replay_dates or not config.experiment.officer_counts:
        typer.echo("Experiment dates and officer counts must be configured.", err=True)
        raise typer.Exit(code=1)

    historical_incidents, _ = LACrimeAdapter(config.data).load()
    output_directory = grouped_data_directory(config.output.directory, "experiments")
    image_output_directory = grouped_image_directory(
        config.output.directory,
        "experiments",
    )
    records = run_experiments(config, historical_incidents, output_directory)
    build_experiment_charts(
        output_directory / "experiments.csv",
        output_directory,
        image_output_directory,
    )

    successful = sum(record.status == "ok" for record in records)
    feasible = sum(record.feasible for record in records)
    valid = sum(record.valid for record in records)
    typer.echo(f"Experiment cases: {len(records):,}")
    typer.echo(f"Feasible cases: {feasible:,}")
    typer.echo(f"Fully successful cases: {successful:,}")
    typer.echo(f"Valid cases: {valid:,}")
    typer.echo(f"Output: {output_directory}")


@app.command("run-baseline-comparison")
def run_baseline_comparison_suite(
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        exists=True,
        dir_okay=False,
        help="Config YAML. Defaults to the selection in configs/default.yaml.",
    ),
) -> None:
    """Compare the full method with greedy and static patrol baselines."""
    config = _load_selected_config(config_path)
    from patrol_planning.experiments.baseline_plots import (
        build_baseline_comparison_charts,
    )

    if not config.comparison.seeds or not config.comparison.officer_counts:
        typer.echo("Comparison seeds and officer counts are required.", err=True)
        raise typer.Exit(code=1)

    historical_incidents, _ = LACrimeAdapter(config.data).load()
    output_directory = grouped_data_directory(
        config.output.directory,
        "baseline_comparison",
    )
    image_output_directory = grouped_image_directory(
        config.output.directory,
        "baseline_comparison",
    )
    records = run_baseline_comparison(
        config,
        historical_incidents,
        output_directory,
    )
    build_baseline_comparison_charts(
        output_directory / "baseline_comparison.csv",
        output_directory,
        image_output_directory,
    )

    expected_cases = len(config.comparison.seeds) * len(
        config.comparison.officer_counts
    )
    proposed = [
        record
        for record in records
        if record.algorithm == "MinP-MaxP-Grafting"
    ]
    typer.echo(f"Sampled scenarios: {expected_cases:,}")
    typer.echo(f"Algorithm results: {len(records):,}")
    typer.echo(
        "Proposed complete-coverage cases: "
        f"{sum(record.complete_coverage for record in proposed):,}/"
        f"{len(proposed):,}"
    )
    typer.echo(
        f"Valid route results: {sum(record.valid for record in records):,}/"
        f"{len(records):,}"
    )
    typer.echo(f"Output: {output_directory}")


@app.command("run-final-evaluation")
def run_final_evaluation_suite(
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        exists=True,
        dir_okay=False,
        help="Config YAML. Defaults to the selection in configs/default.yaml.",
    ),
) -> None:
    """Run the final multi-seed, feasibility, and grid-sensitivity suite."""
    config = _load_selected_config(config_path)
    from patrol_planning.experiments.final_plots import (
        build_final_evaluation_charts,
    )

    historical_incidents, _ = LACrimeAdapter(config.data).load()
    output_directory = grouped_data_directory(
        config.output.directory,
        "final_evaluation",
    )
    image_output_directory = grouped_image_directory(
        config.output.directory,
        "final_evaluation",
    )
    records = run_final_evaluation(
        config,
        historical_incidents,
        output_directory,
    )
    build_final_evaluation_charts(
        output_directory / "final_evaluation.csv",
        output_directory,
        image_output_directory,
    )

    threshold_cases = {
        (record.grid_rows, record.grid_columns, record.seed)
        for record in records
    }
    feasible = sum(record.feasible for record in records)
    valid = sum(record.valid for record in records)
    truncated = sum(record.minp_search_truncated for record in records)
    typer.echo(f"Grid-seed scenarios: {len(threshold_cases):,}")
    typer.echo(f"Officer-count cases: {len(records):,}")
    typer.echo(f"Feasible cases: {feasible:,}")
    typer.echo(f"Valid cases: {valid:,}/{len(records):,}")
    typer.echo(f"Cases with MinP truncation flag: {truncated:,}")
    typer.echo(f"Output: {output_directory}")


if __name__ == "__main__":
    app()
