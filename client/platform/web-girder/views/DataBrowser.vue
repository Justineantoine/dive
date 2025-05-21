<script lang="ts">
import {
  computed, defineComponent, ref, onBeforeUnmount,
} from 'vue';
import {
  getLocationType, GirderModel,
} from '@girder/components/src';
import { useApi } from 'dive-common/apispec';
import { itemsPerPageOptions } from 'dive-common/constants';
import { clientSettings } from 'dive-common/store/settings';
import { useGirderRest } from 'platform/web-girder/plugins/girder';
import { useStore, LocationType, isGirderModel } from '../store/types';
import Upload from './Upload.vue';
import eventBus from '../eventBus';

import DiveGirderBrowser from './DiveGirderBrowser.vue';

export default defineComponent({
  components: {
    DiveGirderBrowser,
    Upload,
  },
  setup() {
    const girderRest = useGirderRest();
    const fileManager = ref();
    const store = useStore();
    const uploading = ref(false);
    const uploaderDialog = ref(false);
    const locationStore = store.state.Location;
    const { getters } = store;
    const { shareData } = useApi();

    function setLocation(location: LocationType) {
      store.dispatch('Location/setRouteFromLocation', location);
    }

    function handleNotification() {
      fileManager.value.$refs.girderBrowser.refresh();
    }

    function updateUploading(newval: boolean) {
      uploading.value = newval;
      if (!newval) {
        fileManager.value.$refs.girderBrowser.refresh();
        uploaderDialog.value = false;
      }
    }

    function isAnnotationFolder(item: GirderModel) {
      return item._modelType === 'folder' && item.meta.annotate;
    }

    function isUserOwner(item: GirderModel) {
      return item.creatorId === girderRest.user._id;
    }

    function isRequestableFolder(item: GirderModel) {
      return isAnnotationFolder(item) && !isUserOwner(item);
    }

    function isSharableFolder(item: GirderModel) {
      return isAnnotationFolder(item) && isUserOwner(item);
    }

    function toggleShare(item: GirderModel) {
      const isShared = !!item.meta.sharedMediaId;
      shareData(item._id, !isShared).then(() => {
        eventBus.$emit('refresh-data-browser');
        //fileManager.value.$refs.girderBrowser.refresh();
      });
    }

    const shouldShowUpload = computed(() => (
      locationStore.location
      && !getters['Location/locationIsViameFolder']
      && getLocationType(locationStore.location) === 'folder'
      && !locationStore.selected.length
      && isGirderModel(locationStore.location)
      && isUserOwner(locationStore.location)
    ));

    const shouldShowNewFolder = computed(() => (
      locationStore.location
      && !getters['Location/locationIsViameFolder']
      && !locationStore.selected.length
      && isGirderModel(locationStore.location)
      && isUserOwner(locationStore.location)
    ));

    const sharedBrowser = computed(() => (
      locationStore.location
      && getLocationType(locationStore.location) === 'collection'
      && isGirderModel(locationStore.location)
      && locationStore.location.name === 'Shared Data'
    ));

    eventBus.$on('refresh-data-browser', handleNotification);
    onBeforeUnmount(() => {
      eventBus.$off('refresh-data-browser', handleNotification);
    });

    return {
      fileManager,
      locationStore,
      getters,
      toggleShare,
      shouldShowUpload,
      shouldShowNewFolder,
      sharedBrowser,
      uploaderDialog,
      uploading,
      clientSettings,
      itemsPerPageOptions,
      /* methods */
      isAnnotationFolder,
      isUserOwner,
      isRequestableFolder,
      isSharableFolder,
      handleNotification,
      setLocation,
      updateUploading,
    };
  },
});
</script>

<template>
  <DiveGirderBrowser
    ref="sharedFileManager"
    v-if="sharedBrowser"
    no-access-control
    :location="locationStore.location"
    :items-per-page.sync="clientSettings.rowsPerPage"
    :items-per-page-options="itemsPerPageOptions"
    @update:location="setLocation($event)"
  >
    <template #row="{ item }">
      <span>{{ item.name }}</span>
      <v-btn
        v-if="isAnnotationFolder(item)"
        class="ml-2"
        x-small
        color="primary"
        depressed
        :to="{ name: 'previewer', params: { id: item._id } }"
      >
        Preview Data
      </v-btn>
      <v-btn
        v-if="isRequestableFolder(item)"
        class="ml-2"
        x-small
        color="primary"
        depressed
      >
        Request Access
      </v-btn>
    </template>
  </DiveGirderBrowser>
  <DiveGirderBrowser
    ref="fileManager"
    v-else
    v-model="locationStore.selected"
    :selectable="!getters['Location/locationIsViameFolder']"
    new-folder-enabled
    :location="locationStore.location"
    :items-per-page.sync="clientSettings.rowsPerPage"
    :items-per-page-options="itemsPerPageOptions"
    @update:location="setLocation($event)"
  >
    <template #headerwidget>
      <v-dialog
        v-if="shouldShowUpload"
        v-model="uploaderDialog"
        max-width="800px"
        :persistent="uploading"
      >
        <template #activator="{ on }">
          <v-btn
            class="ma-0"
            text
            small
            v-on="on"
          >
            <v-icon
              left
              color="accent"
            >
              mdi-file-upload
            </v-icon>
            Upload
          </v-btn>
        </template>
        <Upload
          :location="locationStore.location"
          @update:uploading="updateUploading"
          @close="uploaderDialog = false"
        />
      </v-dialog>
    </template>
    <template #row="{ item }">
      <span>{{ item.name }}</span>
      <v-icon
        v-if="getters['Jobs/datasetRunningState'](item._id)"
        color="warning"
        class="rotate"
      >
        mdi-autorenew
      </v-icon>
      <v-btn
        v-if="isSharableFolder(item)"
        class="ml-2"
        x-small
        color="primary"
        depressed
        :to="{ name: 'viewer', params: { id: item._id } }"
      >
        Launch Annotator
      </v-btn>
      <v-btn
        v-if="isSharableFolder(item) && !item.meta.sharedMediaId"
        class="ml-2"
        x-small
        color="primary"
        depressed
        @click.stop="toggleShare(item)"
      >
        Share
      </v-btn>
      <v-btn
        v-if="isSharableFolder(item) && !!item.meta.sharedMediaId"
        class="ml-2"
        x-small
        rounded
        outlined
        depressed
        @click.stop="toggleShare(item)"
      >
        Unshare
      </v-btn>
      <v-chip
        v-if="(item.foreign_media_id)"
        color="white"
        x-small
        outlined
        disabled
        class="my-0 mx-3"
      >
        cloned
      </v-chip>
      <v-chip
        v-if="(item.meta && item.meta.published)"
        color="green"
        x-small
        outlined
        disabled
        class="my-0 mx-3"
      >
        published
      </v-chip>
    </template>
  </DiveGirderBrowser>
</template>
