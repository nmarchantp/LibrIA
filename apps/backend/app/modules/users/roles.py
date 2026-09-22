"""Tipos de cuenta que muestra el mural."""

from typing import Literal

PublicUserRole = Literal["lector", "influencer", "autor", "libreria"]
UserRole = Literal["lector", "influencer", "autor", "libreria", "admin"]
