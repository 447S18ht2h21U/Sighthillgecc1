/*
 * VERIDIAN application version configuration.
 *
 * Application releases are separate from Master Sales Record versions.
 * The development suffix does not indicate an approved production release.
 */

export const APP_VERSION = '0.1.0-dev';

export const APP_ENVIRONMENT =
  import.meta.env.PROD ? 'Production Build' : 'Local Development';

export const APP_VERSION_LABEL =
  `Version ${APP_VERSION} | ${APP_ENVIRONMENT}`;