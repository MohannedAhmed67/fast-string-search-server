// fastset.c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "uthash.h"

typedef struct
{
    char *key; // line content
    UT_hash_handle hh;
} HashItem;

static HashItem *hash_table = NULL;

void load_file(const char *filename)
{
    FILE *f = fopen(filename, "r");
    if (!f)
        return;

    char line[1024];
    while (fgets(line, sizeof(line), f))
    {
        line[strcspn(line, "\r\n")] = '\0'; // remove newline
        HashItem *item = malloc(sizeof(HashItem));
        item->key = strdup(line);
        HASH_ADD_KEYPTR(hh, hash_table, item->key, strlen(item->key), item);
    }
    fclose(f);
}

int exists(const char *query)
{
    HashItem *result = NULL;
    HASH_FIND_STR(hash_table, query, result);
    return result != NULL;
}
