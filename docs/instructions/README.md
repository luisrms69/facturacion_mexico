# 📋 Instrucciones Internas - Claude Code

**Audiencia:** Claude Code únicamente
**Propósito:** Instrucciones temporales de trabajo durante sesiones de desarrollo
**Visibilidad:** Privado - NO incluido en documentación pública

---

## ⚠️ Importante

Esta carpeta contiene archivos de instrucciones temporales para Claude Code durante el desarrollo activo. **No están destinados a ser documentación pública.**

### Contenido Típico

- `next.md` - Siguiente tarea o error a resolver
- `revisa propuesta.md` - Propuestas de cambios para revisión
- `Haz committ.md` - Instrucciones específicas de commit
- Otros archivos temporales de trabajo

### Exclusión de Documentación

- ❌ **NO incluido en MkDocs** (no aparece en `mkdocs.yml` nav)
- ✅ **Sí incluido en Git** (versionado para continuidad de trabajo)
- ✅ **Solo para uso interno** durante desarrollo

### Limpieza

Estos archivos deben:
- Limpiarse regularmente después de completar tareas
- No acumularse indefinidamente
- Convertirse a documentación formal si son relevantes a largo plazo

---

**Nota:** Si encuentras este directorio en producción/build, fue incluido por error. Debe estar excluido de distribuciones finales.
