from typing import Dict, List, Any, Optional, Set, Tuple
from app.core.logging import logger
from app.utils.email_utils import normalize_email, calculate_bounce_rate


class AggregationService:
    """
    Core aggregation engine for Mailbox-level analytics.

    Responsibilities:
    - Deduplicate mailboxes across campaigns using smartlead_email_account_id or normalized email.
    - Accurately aggregate sent and bounced counts without double-counting.
    - Enforce strict attribution rules (never guess or divide campaign totals across multi-mailbox campaigns).
    - Validate numbers (non-negative, bounce <= sent).
    - Calculate bounce rates rounded to 2 decimal places.
    """

    @staticmethod
    def get_mailbox_key(email: str, email_account_id: Optional[Any] = None) -> str:
        """
        Computes a canonical unique identifier for a mailbox.
        Prefers stringified smartlead_email_account_id if valid, otherwise falls back to normalized email.
        """
        if email_account_id is not None and str(email_account_id).strip() and str(email_account_id).strip() != "None":
            return f"id:{str(email_account_id).strip()}"
        return f"email:{normalize_email(email)}"

    def aggregate_campaign_mailboxes(
        self,
        client_info: Dict[str, Any],
        campaign_mailbox_stats: List[Dict[str, Any]],
        webhook_mailbox_events: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Aggregates mailbox stats across all campaigns for a given client.

        Args:
            client_info: {"client_id": str, "client_name": str}
            campaign_mailbox_stats: List of dicts representing mailbox contributions:
                [
                    {
                        "campaign_id": "101",
                        "campaign_name": "Outreach A",
                        "email": "sales@company.com",
                        "email_account_id": "987",
                        "sent": 300,
                        "bounced": 5,
                        "campaign_mailbox_count": 1,
                        "attribution_status": "direct"
                    },
                    ...
                ]
            webhook_mailbox_events: Optional dict mapping mailbox_key -> {"sent": int, "bounced": int}

        Returns:
            List of aggregated mailbox dicts for the client:
            [
                {
                    "client_id": "123",
                    "client_name": "Client A",
                    "email": "sales@company.com",
                    "mailbox_id": "987",
                    "sent": 500,
                    "bounced": 8,
                    "bounce_rate": 1.60,
                    "campaign_ids": ["101", "102"],
                    "attribution_status": "direct"
                }
            ]
        """
        client_id = str(client_info.get("client_id", "default"))
        client_name = str(client_info.get("client_name", "Default Client"))

        # Map: canonical_key -> accumulator dict
        mailboxes_map: Dict[str, Dict[str, Any]] = {}
        seen_campaign_mailbox_pairs: Set[Tuple[str, str]] = set()

        for entry in campaign_mailbox_stats:
            raw_email = entry.get("email", "")
            raw_acc_id = entry.get("email_account_id") or entry.get("mailbox_id")
            norm_email = normalize_email(raw_email)

            if not norm_email and not raw_acc_id:
                logger.warning(f"Skipping entry missing both email and account_id: {entry}")
                continue

            mb_key = self.get_mailbox_key(norm_email, raw_acc_id)
            camp_id = str(entry.get("campaign_id", ""))

            # Prevent duplicate contributions from the exact same campaign + mailbox record
            pair_key = (camp_id, mb_key)
            if camp_id and pair_key in seen_campaign_mailbox_pairs:
                logger.warning(
                    f"Duplicate campaign-mailbox record detected and ignored: Campaign {camp_id}, Mailbox {mb_key}"
                )
                continue
            if camp_id:
                seen_campaign_mailbox_pairs.add(pair_key)

            sent = int(entry.get("sent", 0))
            bounced = int(entry.get("bounced", 0))
            status = entry.get("attribution_status", "direct")

            # Validate input non-negativity
            if sent < 0:
                logger.warning(f"Negative sent value ({sent}) for mailbox {norm_email}. Sanitizing to 0.")
                sent = 0
            if bounced < 0:
                logger.warning(f"Negative bounced value ({bounced}) for mailbox {norm_email}. Sanitizing to 0.")
                bounced = 0

            if mb_key not in mailboxes_map:
                mailboxes_map[mb_key] = {
                    "client_id": client_id,
                    "client_name": client_name,
                    "email": norm_email,
                    "mailbox_id": str(raw_acc_id) if raw_acc_id else None,
                    "sent": 0,
                    "bounced": 0,
                    "campaign_ids": set(),
                    "attribution_statuses": set(),
                }

            # Update email if missing previously
            if not mailboxes_map[mb_key]["email"] and norm_email:
                mailboxes_map[mb_key]["email"] = norm_email

            # Update mailbox_id if missing previously
            if not mailboxes_map[mb_key]["mailbox_id"] and raw_acc_id:
                mailboxes_map[mb_key]["mailbox_id"] = str(raw_acc_id)

            if camp_id:
                mailboxes_map[mb_key]["campaign_ids"].add(camp_id)

            mailboxes_map[mb_key]["sent"] += sent
            mailboxes_map[mb_key]["bounced"] += bounced
            mailboxes_map[mb_key]["attribution_statuses"].add(status)

        # Check for overriding webhook data if available for higher fidelity
        if webhook_mailbox_events:
            for mb_key, accum in mailboxes_map.items():
                if mb_key in webhook_mailbox_events:
                    wh_data = webhook_mailbox_events[mb_key]
                    accum["sent"] = wh_data.get("sent", accum["sent"])
                    accum["bounced"] = wh_data.get("bounced", accum["bounced"])
                    accum["attribution_statuses"] = {"webhook_tracked"}

        # Build final aggregated list
        aggregated_results: List[Dict[str, Any]] = []
        for mb_key, accum in sorted(mailboxes_map.items(), key=lambda x: x[1]["email"]):
            sent_total = accum["sent"]
            bounced_total = accum["bounced"]
            bounce_rate = calculate_bounce_rate(sent_total, bounced_total)

            # Determine aggregate attribution status
            statuses = accum["attribution_statuses"]
            if "webhook_tracked" in statuses:
                attr_status = "webhook_tracked"
            elif "multi_mailbox_limitation" in statuses and len(statuses) == 1:
                attr_status = "limitation_noted"
            else:
                attr_status = "direct"

            aggregated_results.append({
                "client_id": accum["client_id"],
                "client_name": accum["client_name"],
                "email": accum["email"],
                "mailbox_id": accum["mailbox_id"],
                "sent": sent_total,
                "bounced": bounced_total,
                "bounce_rate": bounce_rate,
                "campaign_ids": sorted(list(accum["campaign_ids"])),
                "attribution_status": attr_status,
            })

        logger.info(
            f"Client {client_name} ({client_id}): Aggregated {len(aggregated_results)} unique mailboxes "
            f"from {len(seen_campaign_mailbox_pairs)} campaign-mailbox mappings."
        )
        return aggregated_results
