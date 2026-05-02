## Qué hace este PR
[Descripción clara de qué cambia y por qué]

## Tipo de cambio
- [ ] Feature — nueva funcionalidad
- [ ] Fix — corrección de bug
- [ ] Hotfix — corrección urgente en producción
- [ ] Migration — cambios de esquema o datos
- [ ] Refactor — sin cambio funcional
- [ ] Docs — solo documentación

## Checklist
- [ ] Tests pasan (`bench --site facturacion.dev run-tests --app facturacion_mexico`)
- [ ] Fixtures exportados si hubo cambios de Custom Fields, Roles, DocPerms, Workflows
- [ ] Patch creado y registrado en patches.txt si hay cambios de esquema con datos
- [ ] Sin secrets en el código (credenciales FacturAPI nunca en git)
- [ ] `bench --site facturacion.dev migrate` limpio en desarrollo
- [ ] Sin rutas hardcodeadas de bench
- [ ] CLAUDE.md actualizado si cambió algo relevante de la app
- [ ] ruff sin errores
- [ ] black sin diferencias

## Lógica fiscal (si aplica)
- [ ] RFC con formato válido
- [ ] Montos a 2 decimales
- [ ] UUID de timbrado no expuesto en logs
- [ ] Flujo de timbrado/cancelación probado manualmente

## Notas para el reviewer
[Contexto adicional, decisiones tomadas, riesgos conocidos]
