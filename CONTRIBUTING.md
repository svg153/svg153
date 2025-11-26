# Contribuir a este repositorio

Aquí se documentan todos los flujos y automatizaciones que mantienen vivo el perfil. El README debe centrarse únicamente en la información personal, así que usa este archivo para cualquier tarea operativa.

## Índice rápido

1. [Automatización de repositorios pineados](#automatización-de-repositorios-pineados)
2. [Actualizaciones dinámicas del README](#actualizaciones-dinámicas-del-readme)
3. [Tokens y buenas prácticas](#tokens-y-buenas-prácticas)

---

## Automatización de repositorios pineados

> Controla qué repos aparecen en la sección "Pinned" del perfil usando `pinned.yml` + un workflow.

### 1. editar `pinned.yml`

- Define el usuario objetivo en `user:` (por defecto `svg153`).
- Lista hasta 6 repositorios en formato `owner/name` bajo `pinned:` (se usará el orden del YAML).

```yml
user: svg153
pinned:
  - svg153/awesome-stars
  - svg153-org/admin
  - EntrevistadorInteligente/admin
  - public-acme/infra
  - svg153/configLinux
  - svg153/docker-demo
```

### 2. acción local `sync-pins`

- La acción vive en `./.github/actions/sync-pins`, expone una imagen Docker propia y ejecuta el script `sync_pins.py`, que desapinea todo y vuelve a pinear según `pinned.yml`.
- Puedes copiar la carpeta (Dockerfile + script) o publicarla como Action dockerizada para reutilizarla en otros repos.

### 3. workflow `sync-pinned.yml`

- Se dispara automáticamente al modificar `pinned.yml` (o la acción) y admite `workflow_dispatch` manual.
- Requiere el secreto `PIN_REPO_TOKEN` con scopes `public_repo` (o `repo` si hay repos privados) y `read:user`.
- Ejecución manual desde CLI: `gh workflow run sync-pinned`.

### 4. ejecución local (opcional)

```bash
PIN_REPO_TOKEN=<token> python .github/actions/sync-pins/sync_pins.py
```

_Si prefieres mantener el flujo completo en GitHub Actions, también puedes disparar el workflow como antes:_

```bash
PIN_REPO_TOKEN=<token> gh workflow run sync-pinned --ref main
```

---

## DevCard de daily.dev

> Renderiza la tarjeta de daily.dev en la rama `devcard` y la embebe en el README.

- Configura el secreto `DEVCARD_ID` con tu identificador (lo obtienes en [https://app.daily.dev/api/id](https://app.daily.dev/api/id)).
- El workflow principal vive en [`devcard.yml`](.github/workflows/devcard.yml), corre a diario, se puede disparar manualmente (`workflow_dispatch`) y solo hace commit si la tarjeta cambia gracias a `dailydotdev/action-devcard@2.3.1`.
- Mientras validamos la migración se mantiene en paralelo la definición original en [`artifacts.yaml`](.github/workflows/artifacts.yaml); ambos apuntan al mismo proceso y pueden convivir temporalmente.
- El archivo se guarda como `devcard.svg` en la rama `devcard`; el README lo consume vía `https://raw.githubusercontent.com/svg153/svg153/devcard/devcard.svg`.
- Ejecución manual desde CLI:
  ```bash
  gh workflow run "DevCard (daily.dev)" --ref main
  ```

---

## Actualizaciones dinámicas del README

> Reemplaza las secciones de YouTube y repos destacados usando la acción local `./.github/actions/update-readme` y el workflow programado.

### 1. `auto_content.yml`

- `youtube.channels`: lista ordenada de canales a mostrar. Cada entrada acepta `id`, `label`, `url`, `heading` y `max_items` (cualquier campo es opcional salvo `id`).
- `youtube.max_items`: valor por defecto de `max_items` para cada canal (se mantiene compatibilidad con los campos históricos `channel_id` / `community_channel_id`).
- `repos.owner`: usuario cuyas estadísticas se usan (por defecto `svg153`).
- `repos.top_new` / `repos.top_active`: límite para cada tabla.
- `repos.active_days`: ventana para considerar actividad reciente.
- `repos.ignore`: lista (o valores separados por comas) de repositorios a excluir de ambas tablas (por ejemplo, `svg153`, `gitbook-example`).

### 2. acción local `./.github/actions/update-readme/update_readme.py`

```bash
cd /path/to/repo
GITHUB_TOKEN=<token con scope repo> python3 .github/actions/update-readme/update_readme.py
```

- Ejecuta exactamente el mismo código que la acción dockerizada y se apoya en PyYAML para leer `auto_content.yml`.
- Llama al RSS oficial de YouTube y a `https://api.github.com/users/<owner>/repos` para generar las listas.
- Sustituye el contenido entre `<!-- YOUTUBE_SECTION_* -->` y `<!-- REPO_SECTION_* -->` en `README.md`.
- Si no hay token, funcionará con limitaciones (rate limits más estrictos).

### 3. workflow `update-readme.yml`

- Corre cada lunes a las 06:00 UTC y también admite `workflow_dispatch` manual.
- Usa `secrets.README_TOKEN` si existe; en su defecto se apoya en `github.token`.
- Tras actualizar el README hace commit automático con `stefanzweifel/git-auto-commit-action`.

### 4. ejecución manual rápida

```bash
gh workflow run update-readme --ref main
```

---

## Tokens y buenas prácticas

| Uso | Scope mínimo | Secreto recomendado |
| --- | --- | --- |
| Acción de pines | `public_repo`, `read:user` | `PIN_REPO_TOKEN` |
| Actualización del README | `repo` (lectura) | `README_TOKEN` |

- Mantén los tokens en la sección de **Actions secrets and variables** → **Repository secrets**.
- Para pruebas locales, exporta variables de entorno (`PIN_REPO_TOKEN`, `GITHUB_TOKEN`). Evita hardcodear valores.
- Antes de contribuir abre un PR describiendo los cambios; recuerda que el README no debe incluir instrucciones operativas. Usa este archivo para documentarlas.
