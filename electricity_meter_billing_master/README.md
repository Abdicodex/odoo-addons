# Electricity Meter Billing Master (Odoo 20)

Master data for an electricity meter billing business, rebuilt from a technical guide (Odoo 19
introspection report) as an independent implementation.

## What it contains
- **Customer types**, **reasons** (activation, deactivation, meter reading update)
- **Geography**: Region > District > Zone > Sub-Zone > Village/Neighbourhood. Zones get a code
  (prefix + 3 digits); sub-zones carry a prefix; collectors and technicians assigned to a sub-zone
  flow down to its villages
- **Transformers**, **meter types** and **sub meter types**
- **Houses** with an auto-generated supply number `ZONE_CODE-SUB_ZONE_PREFIX-SEQ`, status
  (New / Active / Inactive), activation and deactivation wizards with reasons, GPS position and
  owner/grantor details
- **Meter readings**: update wizard (previous/new reading, meter replacement) and full history
- **Customers**: unique customer ID, customer types taken from their houses, supporting documents
- **Employees**: collector / technician flags
- **Zone Report**: opening balance, billed, paid and total due per zone, from posted customer
  invoices and payments of the customers with a house in the zone
- **Meter Reading History Report** (PDF) for a date range

## Not included (needs Odoo Enterprise apps in the original)
Helpdesk integration and the map view (web_map). Houses have a "Map" button that opens the
position in OpenStreetMap instead.
