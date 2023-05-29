import cron from 'node-cron';

cron.schedule(`*/1 * * * *`, async () => {
  console.log(`running your task...`);

  const process = childProcess.spawn('usr/bin/python3', ['/app/main.py']);
  console.log(`task finished ${process}`);
});
