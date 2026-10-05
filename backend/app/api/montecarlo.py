from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MonteCarloRun, Risk, RiskScore, Taxonomy
from app.montecarlo.mitigation import apply_mitigation
from app.montecarlo.simulate import (
    DEFAULT_HORIZON_YEARS,
    DEFAULT_N_SIMS,
    MonteCarloParams,
    default_sigma,
    run_simulation,
)

router = APIRouter(prefix="/risks", tags=["montecarlo"])


class MitigationInput(BaseModel):
    name: str = "custom"
    effectiveness_frequency: float = 0.0
    effectiveness_severity: float = 0.0


class MonteCarloRequest(BaseModel):
    p_annual: float | None = None
    median_severity: float | None = None
    sigma: float | None = None
    horizon_years: int = DEFAULT_HORIZON_YEARS
    n_sims: int = DEFAULT_N_SIMS
    seed: int = 42
    mitigation: MitigationInput | None = None


class MonteCarloRunOut(BaseModel):
    id: int
    params: dict
    seed: int
    n_sims: int
    mean: float
    median: float
    var95: float
    var99: float
    cvar95: float
    cvar99: float
    hist_bins: dict
    exceedance: dict
    mitigation: dict | None


def _require_treat_risk(db: Session, risk_id: int) -> tuple[Risk, RiskScore]:
    risk = db.query(Risk).filter(Risk.id == risk_id).one_or_none()
    if risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    score = db.query(RiskScore).filter(RiskScore.risk_id == risk_id).one_or_none()
    if score is None:
        raise HTTPException(status_code=400, detail="Risk has not been scored yet")
    if score.zone != "treat":
        raise HTTPException(
            status_code=400,
            detail=(
                "Monte Carlo is only available for Treat-zone risks "
                f"(this risk is {score.zone!r})"
            ),
        )
    return risk, score


@router.post("/{risk_id}/montecarlo", response_model=MonteCarloRunOut)
def run_montecarlo(
    risk_id: int, request: MonteCarloRequest, db: Session = Depends(get_db)
) -> MonteCarloRunOut:
    risk, score = _require_treat_risk(db, risk_id)

    p_annual = request.p_annual if request.p_annual is not None else score.p_mean
    median_severity = (
        request.median_severity if request.median_severity is not None else score.impact_usd
    )
    sigma = request.sigma if request.sigma is not None else default_sigma(median_severity)

    params = MonteCarloParams(
        p_annual=p_annual,
        median_severity=median_severity,
        sigma=sigma,
        horizon_years=request.horizon_years,
        n_sims=request.n_sims,
        seed=request.seed,
    )

    mitigation_json = None
    if request.mitigation is not None:
        params = apply_mitigation(
            params,
            request.mitigation.effectiveness_frequency,
            request.mitigation.effectiveness_severity,
        )
        mitigation_json = request.mitigation.model_dump()

    _losses, result = run_simulation(params)

    taxonomy = (
        db.query(Taxonomy).filter(Taxonomy.id == risk.category_id).one_or_none()
        if risk.category_id
        else None
    )
    params_json = {
        "p_annual": p_annual,
        "median_severity": median_severity,
        "sigma": sigma,
        "lam": params.lam,
        "horizon_years": params.horizon_years,
        "category_group": taxonomy.group if taxonomy else None,
    }

    run = MonteCarloRun(
        risk_id=risk_id,
        params_json=params_json,
        seed=params.seed,
        n_sims=params.n_sims,
        mean=result.mean,
        median=result.median,
        var95=result.var95,
        var99=result.var99,
        cvar95=result.cvar95,
        cvar99=result.cvar99,
        hist_bins_json=result.hist_bins,
        exceed_json=result.exceedance,
        mitigation_json=mitigation_json,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return MonteCarloRunOut(
        id=run.id,
        params=params_json,
        seed=run.seed,
        n_sims=run.n_sims,
        mean=run.mean,
        median=run.median,
        var95=run.var95,
        var99=run.var99,
        cvar95=run.cvar95,
        cvar99=run.cvar99,
        hist_bins=run.hist_bins_json,
        exceedance=run.exceed_json,
        mitigation=run.mitigation_json,
    )


@router.get("/{risk_id}/mc-runs", response_model=list[MonteCarloRunOut])
def list_montecarlo_runs(risk_id: int, db: Session = Depends(get_db)) -> list[MonteCarloRunOut]:
    runs = (
        db.query(MonteCarloRun)
        .filter(MonteCarloRun.risk_id == risk_id)
        .order_by(MonteCarloRun.created_at.desc())
        .all()
    )
    return [
        MonteCarloRunOut(
            id=r.id,
            params=r.params_json,
            seed=r.seed,
            n_sims=r.n_sims,
            mean=r.mean,
            median=r.median,
            var95=r.var95,
            var99=r.var99,
            cvar95=r.cvar95,
            cvar99=r.cvar99,
            hist_bins=r.hist_bins_json,
            exceedance=r.exceed_json,
            mitigation=r.mitigation_json,
        )
        for r in runs
    ]
