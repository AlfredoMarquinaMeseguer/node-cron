import cron from 'node-cron';
import * as childProcess from 'child_process';

cron.schedule(`*/1 * * * *`, async () => {
  console.log(`running your task...`);

  const process = childProcess.spawn('usr/bin/python3', ['/app/main.py']);
  console.log(`task finished ${process}`);
});
