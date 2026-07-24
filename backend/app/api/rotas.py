"""CRUD de rotas e paradas — hierarquia Tenant -> Rotas -> Paradas (Sprint 1).

Paradas usam geolocalização PostGIS (`geo`, POINT/SRID 4326). A API expõe
latitude/longitude (mais natural para o painel do gestor e para o app
motorista) e converte para/de `Geometry` aqui — o motor de ETA (Sprint 2)
consome a coluna `geo` diretamente via PostGIS.

`Parada` não carrega `tenant_id` própria (herda o isolamento da `Rota` via
`rota_id` — ver migration 0001 e arquitetura.md, seção 5); por isso toda
operação de parada primeiro carrega a rota (que passa pela RLS) e valida o
vínculo, fechando o isolamento entre tenants também para paradas.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.shape import to_shape
from shapely import Point
from shapely.geometry import mapping
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_db, require_role
from app.models.rota import Parada, Rota
from app.schemas.cadastros import (
    ParadaCreate,
    ParadaOut,
    ParadaUpdate,
    RotaCreate,
    RotaOut,
    RotaUpdate,
)

router = APIRouter(prefix="/api/rotas", tags=["cadastros:rotas"])

_ROTA_NAO_ENCONTRADA = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rota não encontrada.")
_PARADA_NAO_ENCONTRADA = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parada não encontrada.")


# ---------------------------------------------------------------------------
# Helpers — conversão de geometria PostGIS <-> lat/lon
# ---------------------------------------------------------------------------


def _geo_to_latlon(geo) -> tuple[float, float]:
    point = to_shape(geo)
    return point.y, point.x  # (latitude, longitude)


def _latlon_to_geo(latitude: float, longitude: float) -> str:
    # WKT com SRID — geoalchemy2/psycopg aceita a string EWKT diretamente na
    # coluna Geometry; o Postgres converte e valida o SRID na escrita.
    return f"SRID=4326;{mapping(Point(longitude, latitude))['type'].upper()}({longitude} {latitude})"


def _parada_out(parada: Parada) -> ParadaOut:
    lat, lon = _geo_to_latlon(parada.geo)
    return ParadaOut(
        id=parada.id,
        rota_id=parada.rota_id,
        nome=parada.nome,
        endereco=parada.endereco,
        ordem_base=parada.ordem_base,
        latitude=lat,
        longitude=lon,
        created_at=parada.created_at,
        updated_at=parada.updated_at,
    )


def _get_rota_or_404(db: Session, rota_id: uuid.UUID) -> Rota:
    rota = db.get(Rota, rota_id)
    if rota is None:
        raise _ROTA_NAO_ENCONTRADA
    return rota


def _get_parada_or_404(db: Session, rota: Rota, parada_id: uuid.UUID) -> Parada:
    parada = db.get(Parada, parada_id)
    if parada is None or parada.rota_id != rota.id:
        raise _PARADA_NAO_ENCONTRADA
    return parada


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------


@router.get("", response_model=list[RotaOut])
def listar_rotas(
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> list[Rota]:
    return list(db.scalars(select(Rota).order_by(Rota.nome)))


@router.post("", response_model=RotaOut, status_code=status.HTTP_201_CREATED)
def criar_rota(
    payload: RotaCreate,
    db: Session = Depends(get_tenant_db),
    user=Depends(require_role("admin")),
) -> Rota:
    rota = Rota(tenant_id=user.tenant_id, **payload.model_dump())
    db.add(rota)
    db.commit()
    db.refresh(rota)
    return rota


@router.get("/{rota_id}", response_model=RotaOut)
def obter_rota(
    rota_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> Rota:
    return _get_rota_or_404(db, rota_id)


@router.patch("/{rota_id}", response_model=RotaOut)
def atualizar_rota(
    rota_id: uuid.UUID,
    payload: RotaUpdate,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> Rota:
    rota = _get_rota_or_404(db, rota_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(rota, campo, valor)
    db.commit()
    db.refresh(rota)
    return rota


@router.delete("/{rota_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_rota(
    rota_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> None:
    rota = _get_rota_or_404(db, rota_id)
    db.delete(rota)  # cascade remove paradas (ondelete="CASCADE" na FK)
    db.commit()


# ---------------------------------------------------------------------------
# Paradas (aninhadas em /api/rotas/{rota_id}/paradas)
# ---------------------------------------------------------------------------


@router.get("/{rota_id}/paradas", response_model=list[ParadaOut])
def listar_paradas(
    rota_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> list[ParadaOut]:
    rota = _get_rota_or_404(db, rota_id)
    paradas = db.scalars(
        select(Parada).where(Parada.rota_id == rota.id).order_by(Parada.ordem_base)
    )
    return [_parada_out(p) for p in paradas]


@router.post("/{rota_id}/paradas", response_model=ParadaOut, status_code=status.HTTP_201_CREATED)
def criar_parada(
    rota_id: uuid.UUID,
    payload: ParadaCreate,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> ParadaOut:
    rota = _get_rota_or_404(db, rota_id)
    dados = payload.model_dump(exclude={"latitude", "longitude"})
    parada = Parada(
        rota_id=rota.id,
        geo=_latlon_to_geo(payload.latitude, payload.longitude),
        **dados,
    )
    db.add(parada)
    db.commit()
    db.refresh(parada)
    return _parada_out(parada)


@router.get("/{rota_id}/paradas/{parada_id}", response_model=ParadaOut)
def obter_parada(
    rota_id: uuid.UUID,
    parada_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> ParadaOut:
    rota = _get_rota_or_404(db, rota_id)
    parada = _get_parada_or_404(db, rota, parada_id)
    return _parada_out(parada)


@router.patch("/{rota_id}/paradas/{parada_id}", response_model=ParadaOut)
def atualizar_parada(
    rota_id: uuid.UUID,
    parada_id: uuid.UUID,
    payload: ParadaUpdate,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> ParadaOut:
    rota = _get_rota_or_404(db, rota_id)
    parada = _get_parada_or_404(db, rota, parada_id)

    dados = payload.model_dump(exclude_unset=True)
    lat = dados.pop("latitude", None)
    lon = dados.pop("longitude", None)
    for campo, valor in dados.items():
        setattr(parada, campo, valor)
    if lat is not None or lon is not None:
        atual_lat, atual_lon = _geo_to_latlon(parada.geo)
        parada.geo = _latlon_to_geo(lat if lat is not None else atual_lat, lon if lon is not None else atual_lon)

    db.commit()
    db.refresh(parada)
    return _parada_out(parada)


@router.delete("/{rota_id}/paradas/{parada_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_parada(
    rota_id: uuid.UUID,
    parada_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> None:
    rota = _get_rota_or_404(db, rota_id)
    parada = _get_parada_or_404(db, rota, parada_id)
    db.delete(parada)
    db.commit()
