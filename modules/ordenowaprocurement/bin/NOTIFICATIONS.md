# Procurement event notification scheduler

After the module schema is installed, configure the native shop mail transport and the existing `kuraneapush` live provider, consent notice, customer consent/subscriptions, and PROCUREMENT/POINTS event settings. Keep native password reset mail enabled. Run on the private application server with its normal environment and configured secrets:

```sh
php modules/ordenowaprocurement/bin/dispatch-notifications.php --shop=1 --channels=mail,push --limit=25
```

Schedule this command once per minute for each explicit shop. `--channels` is required; `mail` and `push` can also run independently. No scheduler or production configuration is installed by this change. The command prints only aggregate status counts. The in-app notification record remains available regardless of external delivery state.

Per-channel claims commit before transport calls. A connection advisory lock prevents concurrent workers from sending the same claim. Definite failure retries after 60, 120, 240, or 480 seconds, up to five attempts. Success is never automatically repeated. An interrupted claim or an exception with an unknown transmission outcome becomes `UNCERTAIN`; inspect the provider/mail receipt before deciding whether to resend. A private operator can explicitly acknowledge potential duplicate delivery:

```sh
php modules/ordenowaprocurement/bin/dispatch-notifications.php --shop=1 --channels=mail --retry-uncertain=DELIVERY_ID --ack-possible-duplicate --limit=25
```

Manual retry preserves the attempt count and the five-attempt limit. `FAILED` requires operational investigation. Event mail contains a generic notice and a generated same-shop workspace login link; it contains no balance, award amount, product snapshot, customer name or password reset changes. An ineligible/deactivated/wrong-shop recipient is skipped. Unsupported native locales are skipped rather than sending an unrelated translation.
