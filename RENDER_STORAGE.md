# Render storage

The application ships with a recoverable SQLite snapshot in `the_cup_v31.db`.
Without persistent storage, Render can restore that snapshot on each deploy, but
changes made while the service is running can still disappear after a restart or
redeploy.

## Persistent SQLite setup

1. Upgrade the Render web service to a plan that supports persistent disks.
2. Add a disk to the service with mount path `/var/data`.
3. Add this environment variable:

   ```text
   THE_CUP_DATA_DIR=/var/data
   ```

4. Deploy the service.

On the first start with an empty disk, the app copies the bundled database,
generated team logos, and logo metadata into the mounted directory. Existing
files on the disk are never overwritten during later deploys.

Generated images keep their existing public URLs under
`/static/generated_logos/...`; the application serves those URLs from the
configured runtime directory.

## Free-plan limitation

Render's free web-service filesystem is ephemeral. The bundled database and
tracked assets will make the application usable after a deploy, but new local
SQLite writes and generated images are not durable without a persistent disk.
