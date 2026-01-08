# modules/admin_api.py
from modules.db import get_db

def get_all_orders():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            orders_id, users_id, nama, cluster, blok, no_rumah,
            nomor_antrian, total_harga, metode_pembayaran,
            status, created_at, queue_id
        FROM orders
        ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return rows

def get_order_items(orders_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT nama_item, qty, harga_satuan, total_harga
        FROM order_items
        WHERE orders_id=%s
        ORDER BY order_items_id ASC
    """, (orders_id,))

    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return rows

def update_order_status(orders_id, status):
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "UPDATE orders SET status=%s WHERE orders_id=%s",
        (status, orders_id)
    )
    db.commit()

    cursor.close()
    db.close()
    return True

def delete_order(orders_id):
    db = get_db()
    cursor = db.cursor()
    try:
        db.start_transaction()

        cursor.execute("DELETE FROM order_items WHERE orders_id=%s", (orders_id,))
        cursor.execute("DELETE FROM orders WHERE orders_id=%s", (orders_id,))

        db.commit()
        return True, None

    except Exception as e:
        db.rollback()
        return False, str(e)

    finally:
        cursor.close()
        db.close()
