"""Errores de dominio independientes de HTTP."""


class EmailAlreadyRegisteredError(Exception):
    """El correo ya pertenece a otra cuenta."""


class InvalidCredentialsError(Exception):
    """Correo o contraseña incorrectos."""
